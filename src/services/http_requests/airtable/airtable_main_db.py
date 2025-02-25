import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, List
import pytz

from sncl import AirtableAsync
from config.env import AIRTABLE_API_KEY
from utils.logger import logger
from utils.redis.redis_handler import RedisHandler

# Import the concurrency-limiter-instance
from services.http_requests.airtable.airtable_limiter import airtable_limiter

# Import our new helper
from services.agents.helper_functions import UserContextFile

class AirtableLatteDB:
    """
    AirtableLatteDB with Redis as the primary short-term store, and
    background batched updates to Airtable. Concurrency & rate-limiting
    are enforced by AirtableRateLimiter, ensuring only one request
    at a time and max 5 requests/second.
    """

    # -------------------------------------------------------------------------
    # Airtable config
    # -------------------------------------------------------------------------
    BASE_ID = "appCEmKh65yHFkUhK"
    table_id = "tblUtCZvAqtkn264n"

    # Underlying async Airtable client
    _at = AirtableAsync(base_id=BASE_ID, api_key=AIRTABLE_API_KEY)

    # Our global concurrency + rate-limiter
    _limiter = airtable_limiter
    # -------------------------------------------------------------------------
    # Asyncio Queues for batch updates
    # -------------------------------------------------------------------------
    registration_queue: asyncio.Queue = asyncio.Queue()
    opt_update_queue: asyncio.Queue = asyncio.Queue()
    opt_out_queue: asyncio.Queue = asyncio.Queue()
    thread_update_queue: asyncio.Queue = asyncio.Queue()

    _max_batch_size = 10        # Up to 10 records per Airtable batch
    _batch_timeout = 2.0        # Wait up to 2 seconds to gather a partial batch

    # Optional caches if needed (per the old code):
    _user_cache = {}
    _last_cache_update = {}
    _threads_cache = {}
    _threads_cache_update = {}

    # =========================================================================
    # SECTION A: Start the Background Consumers
    # =========================================================================
    @classmethod
    def start_background_tasks(cls):
        """
        Called once (e.g., in FastAPI startup) to spawn consumers
        for each queue. These run forever in the background.
        """
        asyncio.create_task(cls._registration_consumer(), name="registration_consumer")
        asyncio.create_task(cls._opt_update_consumer(), name="opt_update_consumer")
        asyncio.create_task(cls._opt_out_consumer(), name="opt_out_consumer")
        asyncio.create_task(cls._thread_update_consumer(), name="thread_update_consumer")

    # =========================================================================
    # SECTION B: Data Retrieval (Redis => fallback => Airtable)
    # =========================================================================
    @classmethod
    async def get_user_data(cls, waid: str) -> Optional[Dict]:
        """
        Retrieve user data from Redis; if missing, fetch from Airtable,
        store to Redis (TTL=1800s), and return.
        
        NEW: If data must be fetched from Airtable, create (or refresh) the user context file.
        """
        redis_data = await RedisHandler.get_user_data(waid)
        logger.debug(f"[get_user_data] waid:{waid} - Redis data: {redis_data}")
        if redis_data:
            await RedisHandler.update_user_field(
                waid,
                field="last_user_message_recieved",
                value=datetime.now(pytz.timezone('America/Bogota')).isoformat()
            )
            return redis_data

        # Not in Redis => fallback to Airtable
        try:
            filter_formula = f"{{waid}}='{waid}'"
            logger.debug(f"[get_user_data] waid:{waid} - Filter formula: {filter_formula}")
            result = await cls._limiter.call(
                cls._at.fetch_filtered_records,
                table_id=cls.table_id,
                filter_formula=filter_formula,
                json_format=True
            )
            logger.debug(f"[get_user_data] waid:{waid} - Airtable result: {result}")

            if result and result.get("records"):
                record = result["records"][0]
                user_data = {
                    "record_id": record.get("record_id"),
                    "waid": waid,
                    "Nombre": record.get("Nombre"),
                    "Tipo de Identificación": record.get("Tipo de Identificación"),
                    "# de Identificación": record.get("# de Identificación"),
                    "Fecha de Nacimiento": record.get("Fecha de Nacimiento"),
                    "Edad": record.get("Edad"),
                    "Signo Zodiacal": record.get("Signo"),
                    "Género": record.get("Género"),
                    "País": record.get("País"),
                    "Ciudad": record.get("Ciudad"),
                    "Preferencias": record.get("Notas"),
                    "opt_out": record.get("opt_out", "opt-in"),
                    "opt_out_last_updated": record.get("opt_out_last_updated"),
                    "agent_threads": record.get("agent_threads"),
                    "last_user_message_recieved": datetime.now(pytz.timezone('America/Bogota')).isoformat(),

                    # The field in Airtable that might store the file ID:
                    ## This fields are for handling the user's context file for the agent
                    "user_context_file_id": record.get("user_context_file_id", ""),
                    "session_status": "New Session"  
                }

                # ----------------------------------------------------------------
                # (A) Create or Refresh the user's context file on OpenAI
                # ----------------------------------------------------------------
                new_file_id = await UserContextFile.sync_user_context_file(user_data)
                user_data["user_context_file_id"] = new_file_id

                # ----------------------------------------------------------------
                # (B) Store updated user_data in Redis
                # ----------------------------------------------------------------
                await RedisHandler.create_user_record(waid, user_data)

                # ----------------------------------------------------------------
                # (C) Enqueue an update for the "user_context_file_id" field
                # ----------------------------------------------------------------
                record_id = user_data.get("record_id")
                if record_id and new_file_id:
                    update_record = {
                        "id": record_id,
                        "fields": {"user_context_file_id": new_file_id}
                    }
                    await cls.opt_update_queue.put(update_record)

                return user_data

            return None
        except Exception as e:
            logger.error(f"[get_user_data] waid:{waid} - Error fetching from Airtable: {e}")
            return None

    # =========================================================================
    # SECTION C: Create / Update Users (Redis => Enqueue => Airtable)
    # =========================================================================
    @classmethod
    async def register_user(cls, waid: str, data: dict) -> None:
        """
        1) Store new user in Redis.
        2) Enqueue a create-record for the 'registration_queue'.
        """
        # Write to Redis
        user_data = {
            "waid": waid,
            "full_name": data["full_name"],
            "id_number": data["id_number"],
            "id_type": data["id_type"],
            "birth_date": data["birth_date"],
            "more_about": data["more_about"],
            "opt_out": "opt-in",

            # The field in Airtable that might store the file ID:
            ## This fields are for handling the user's context file for the agent
            "user_context_file_id": "",
            "session_status": "New Session"  
        }
        await RedisHandler.create_user_record(waid, user_data)

        # Enqueue for later batch create
        airtable_record = {
            "fields": {
                "Nombre": data["full_name"],
                "# de Identificación": int(data["id_number"]),
                "Tipo de Identificación": {
                    "CC": "Cédula de Ciudadanía",
                    "CE": "Cédula de Extranjería",
                    "PASAPORTE": "Pasaporte"
                }[data["id_type"]],
                "Fecha de Nacimiento": data["birth_date"],
                "WhatsApp": waid,
                "Notas": data["more_about"],
                "Tratamiento De Datos": "Autorizo",
                "opt_out": "opt-in",
            }
        }
        await cls.registration_queue.put(airtable_record)

    @classmethod
    async def update_user_opt_status(cls, waid: str, new_status: str) -> None:
        """
        1) Update user in Redis.
        2) Enqueue a partial-update to Airtable if record_id is known.
        """
        user_data = await RedisHandler.get_user_data(waid)
        if not user_data:
            logger.warning(f"[update_user_opt_status] waid:{waid} - No user data in Redis.")
            return

        user_data["opt_out"] = new_status
        await RedisHandler.create_user_record(waid, user_data)

        record_id = user_data.get("record_id")
        if record_id:
            update_record = {
                "id": record_id,
                "fields": {"opt_out": new_status}
            }
            await cls.opt_update_queue.put(update_record)
        else:
            logger.debug(f"[update_user_opt_status] waid:{waid} - No record_id; skipping enqueue.")

    @classmethod
    async def opt_out_user(cls, waid: str) -> None:
        """
        1) Mark user as 'opt-out' in Redis.
        2) Enqueue an update if record_id is known.
        """
        user_data = await RedisHandler.get_user_data(waid)
        if not user_data:
            logger.warning(f"[opt_out_user] waid:{waid} - No user data in Redis.")
            return

        user_data["opt_out"] = "opt-out"
        await RedisHandler.create_user_record(waid, user_data)

        record_id = user_data.get("record_id")
        if record_id:
            update_record = {
                "id": record_id,
                "fields": {"opt_out": "opt-out"}
            }
            await cls.opt_out_queue.put(update_record)
        else:
            logger.debug(f"[opt_out_user] waid:{waid} - No record_id; skipping enqueue.")

    # =========================================================================
    # SECTION D: Threads Handling
    # =========================================================================
    @classmethod
    async def save_user_threads(cls, user_waid: str, threads_data: dict) -> None:
        """
        Update agent_threads for the user identified by user_waid both in Redis and Airtable.
        This method updates the thread data in Redis and, if a record_id exists, enqueues an update
        to Airtable.
        """
        # Retrieve the full user data from Redis based on waid
        user_data = await RedisHandler.get_user_data(user_waid)
        if not user_data:
            logger.error(f"[save_user_threads] waid:{user_waid} - No user data found in Redis.")
            return

        # Update Redis with the new threads data
        user_data["agent_threads"] = threads_data
        await RedisHandler.create_user_record(user_waid, user_data)

        # If we have a record_id, enqueue an update for Airtable
        record_id = user_data.get("record_id")
        if record_id:
            update_record = {
                "id": record_id,
                "fields": {"agent_threads": json.dumps(threads_data)}
            }
            await cls.thread_update_queue.put(update_record)
            logger.info(f"[save_user_threads] waid:{user_waid} - Enqueued Airtable update, record_id:{record_id}")
        else:
            logger.warning(f"[save_user_threads] waid:{user_waid} - No record_id found in user data.")

    @classmethod
    async def get_user_threads(cls, user_waid: str) -> Optional[dict]:
        """
        Return 'agent_threads' from Redis (or from Airtable via get_user_data) and update Redis if necessary.
        """
        user_data = await cls.get_user_data(user_waid)
        if not user_data:
            logger.debug(f"[get_user_threads] waid:{user_waid} - No data in Redis/Airtable.")
            return None

        threads = user_data.get("agent_threads")
        if threads:
            # If the threads are stored as a string, decode it
            if isinstance(threads, str):
                try:
                    threads = json.loads(threads)
                    user_data["agent_threads"] = threads
                    await RedisHandler.create_user_record(user_waid, user_data)
                except json.JSONDecodeError:
                    logger.error(f"[get_user_threads] waid:{user_waid} - Error decoding agent_threads.")
                    threads = {}
            return threads

        # No threads present; update Redis with an empty dict and return it
        user_data["agent_threads"] = {}
        await RedisHandler.create_user_record(user_waid, user_data)
        return {}

    # =========================================================================
    # SECTION E: Background Consumers for Each Queue
    # =========================================================================
    @classmethod
    async def _registration_consumer(cls):
        """Forever consume from registration_queue in batches."""
        while True:
            await cls._process_batch(cls.registration_queue, cls._at_create_records)
            await asyncio.sleep(0.1)

    @classmethod
    async def _opt_update_consumer(cls):
        """Forever consume from opt_update_queue in batches."""
        while True:
            await cls._process_batch(cls.opt_update_queue, cls._at_update_multiple_records)
            await asyncio.sleep(0.1)

    @classmethod
    async def _opt_out_consumer(cls):
        """Forever consume from opt_out_queue in batches."""
        while True:
            await cls._process_batch(cls.opt_out_queue, cls._at_update_multiple_records)
            await asyncio.sleep(0.1)

    @classmethod
    async def _thread_update_consumer(cls):
        """Forever consume from thread_update_queue in batches."""
        while True:
            await cls._process_batch(cls.thread_update_queue, cls._at_update_multiple_records)
            await asyncio.sleep(0.1)

    @classmethod
    async def _process_batch(cls, queue: asyncio.Queue, handler_func):
        """
        Retrieve up to _max_batch_size items from the given queue,
        or until _batch_timeout seconds, then call handler_func(items).
        """
        items = []
        start_time = time.time()

        while True:
            timeout = cls._batch_timeout - (time.time() - start_time)
            if timeout <= 0:
                break

            try:
                item = await asyncio.wait_for(queue.get(), timeout=timeout)
                items.append(item)
                queue.task_done()
            except asyncio.TimeoutError:
                break

            if len(items) >= cls._max_batch_size:
                break

        if items:
            try:
                await handler_func(items)
            except Exception as e:
                logger.error(f"[batch] Error in processing batch: {e}")
                # Optional: re-queue items or handle partial failures
                pass

    # =========================================================================
    # SECTION F: Actual Airtable calls (via RateLimiter)
    # =========================================================================
    @classmethod
    async def _at_create_records(cls, items: List[dict]) -> None:
        """
        Create up to _max_batch_size new records (registration) in Airtable, then update
        record_ids in Redis if needed.

        Each item should already be a dict with the key "fields" as created by register_user_airtable.
        """
        waids = list({item.get("fields", {}).get("WhatsApp") for item in items if item.get("fields", {}).get("WhatsApp")})
        logger.debug(f"[create_records] waid:{waids} - Creating records: {items}")

        # Pass the list directly to the create_records function
        response = await cls._limiter.call(
            cls._at.create_records,
            table_id=cls.table_id,
            records=items,  # <-- Directly pass the list
            typecast=True
        )
        
        if not response:
            logger.error("[create_records] No response received from Airtable")
            return

        # Check response type and get list of created records
        if isinstance(response, list):
            created_records = response
        else:
            created_records = response.get("records", [])

        for r in created_records:
            record_id = r.get("id")
            fields = r.get("fields", {})
            waid = fields.get("WhatsApp")
            if record_id and waid:
                redis_data = await RedisHandler.get_user_data(waid)
                if redis_data:
                    redis_data["record_id"] = record_id
                    await RedisHandler.create_user_record(waid, redis_data)

        logger.info(f"[create_records] waid:{waids} - Created {len(items)} records in Airtable.")

    @classmethod
    async def _at_update_multiple_records(cls, items: List[dict]) -> None:
        """
        Update up to 10 records in Airtable (opt_in, opt_out, threads, etc.).
        """
        waids = list({item.get("fields", {}).get("WhatsApp") for item in items if item.get("fields", {}).get("WhatsApp")})
        if waids:
            logger.debug(f"[update_multiple_records] waid:{waids} - Updating: {items}")
        else:
            logger.debug(f"[update_multiple_records] Updating: {items}")
            
        await cls._limiter.call(
            cls._at.update_multiple_records,
            table_id=cls.table_id,
            records=items,
            typecast=True
        )
        
        if waids:
            logger.info(f"[update_multiple_records] waid:{waids} - Updated {len(items)} records in Airtable.")
        else:
            logger.info(f"[update_multiple_records] Updated {len(items)} records in Airtable.")

    # =========================================================================
    # SECTION G: (Optional) Clear local caches
    # =========================================================================
    @classmethod
    async def clear_caches(cls):
        cls._user_cache.clear()
        cls._last_cache_update.clear()
        cls._threads_cache.clear()
        cls._threads_cache_update.clear()

    @classmethod
    def get_template_lock_status(cls, waid: str) -> bool:
        """
        Example leftover from older logic. If you rely on class-level _user_cache,
        this just reads from that local dictionary (not Redis).
        """
        logger.debug(f"waid:{waid} - Checking template lock status.")
        if waid in cls._user_cache:
            user_data = cls._user_cache[waid]
            lock_status = user_data.get('fields', {}).get('locked_on_template_flow', False)
            logger.debug(f"waid:{waid} - Lock status: {lock_status}")
            return lock_status

        logger.debug(f"waid:{waid} - No cache data found.")
        return False