import json
from services.http_requests.airtable.airtable_main_db import AirtableLatteDB
from utils.logger import logger
from utils.redis.redis_handler import RedisHandler

class UserThreads:
    @staticmethod
    async def load_threads(user_waid: str) -> dict:
        """
        Load the thread IDs for the given user_waid by retrieving the 
        'agent_threads' from user data stored in Redis (or falling back to Airtable).
        Returns a dict like:
        {
          "main_thread": "<main_thread_id>",
          "agent_name_1": {
             "other_agent_1": "<thread_id>",
             "other_agent_2": "<thread_id>"
          }
        }
        If no record is found, returns an empty dict.
        """
        logger.debug(f"Loading threads for user {user_waid}")
        try:
            threads_data = await AirtableLatteDB.get_user_threads(user_waid)
            if threads_data is None:
                logger.debug(f"No threads found for user {user_waid}; returning empty dict.")
                return {}
            logger.debug(f"Loaded threads data for user {user_waid}: {threads_data}")
            return threads_data
        except Exception as e:
            logger.error(f"Error loading threads for user {user_waid}: {str(e)}")
            return {}

    @staticmethod
    async def save_threads(user_waid: str, new_threads: dict) -> None:
        """
        Save the given threads dictionary for the specified user by:
        
        1) Retrieving the user's current data from Redis.
        2) Comparing the current agent_threads with new_threads.
        3) If there are changes, calling AirtableLatteDB.save_user_threads (which updates both Redis
           and enqueues an update to Airtable).
        
        new_threads looks like:
        {
          "main_thread": "<main_thread_id>",
          "agent_name_1": {
            "other_agent_1": "<thread_id>",
            "other_agent_2": "<thread_id>"
          }
        }
        """
        logger.debug(f"Saving threads for user {user_waid}")
        try:
            user_data = await RedisHandler.get_user_data(user_waid)
            if not user_data:
                raise ValueError(f"No user data found for user {user_waid} in Redis.")
            
            current_threads = user_data.get("agent_threads") or {}
            logger.debug(f"Current threads for user {user_waid}: {current_threads}")
            logger.debug(f"New threads for user {user_waid}: {new_threads}")

            # If threads haven't changed, skip the update.
            if new_threads == current_threads:
                logger.debug(f"Threads haven't changed for user {user_waid}; skipping save.")
                return

            # Update threads via AirtableLatteDB (which writes to Redis and enqueues update to Airtable)
            await AirtableLatteDB.save_user_threads(user_waid, new_threads)
            logger.debug(f"Threads saved for user {user_waid} and update enqueued successfully.")

        except Exception as e:
            logger.error(f"Error saving threads for user {user_waid}: {str(e)}")
            raise

    @staticmethod
    async def delete_threads(user_waid: str) -> None:
        """
        Delete the agent_threads field from the user's record in Redis so a new thread 
        will be generated on the next call.
        """
        logger.debug(f"Deleting threads for user {user_waid} from Redis")
        try:
            # Build the Redis key from the waid (as stored in the Redis hash)
            user_key = f"waid:{user_waid}"
            result = await RedisHandler.delete_hash_field(user_key, "agent_threads")
            if result:
                logger.debug(f"Successfully deleted threads for user {user_waid}.")
            else:
                logger.debug(f"No threads found to delete for user {user_waid}.")
        except Exception as e:
            logger.error(f"Error deleting threads for user {user_waid}: {str(e)}")