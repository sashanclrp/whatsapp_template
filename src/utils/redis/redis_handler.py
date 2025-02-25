from typing import Any, Optional, Dict, List
from datetime import datetime
from utils.logger import logger
from utils.redis.aioredis import RedisClient
import json

class RedisHandler:
    DEFAULT_TTL = 86400  # 24 hours in seconds
    HANDLER_TTL = 86400  # 24 hours in seconds
    TEMPLATE_TTL = 86400  # 24 hours in seconds

    # Basic Key-Value Operations
    @staticmethod
    async def set(key: str, value: Any, ex: int = None) -> bool:
        """Store data in Redis with optional expiration"""
        async with RedisClient.connection() as redis:
            try:
                serialized = json.dumps(value)
                return await redis.set(key, serialized, ex=ex)
            except (TypeError, json.JSONDecodeError) as e:
                logger.error(f"Serialization error for key {key}: {str(e)}")
                raise

    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """Retrieve data from Redis"""
        async with RedisClient.connection() as redis:
            data = await redis.get(key)
            if data:
                try:
                    return json.loads(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Deserialization error for key {key}: {str(e)}")
                    return None
            return None

    @staticmethod
    async def delete(key: str) -> int:
        """Delete a key from Redis"""
        async with RedisClient.connection() as redis:
            return await redis.delete(key)
        
    @staticmethod
    async def keys(pattern: str) -> List[str]:
        """Retrieve a list of keys matching the given pattern."""
        async with RedisClient.connection() as redis:
            return await redis.keys(pattern)

    # TTL Management
    @staticmethod
    async def get_ttl(key: str) -> int:
        """Get remaining TTL for a hash"""
        async with RedisClient.connection() as redis:
            try:
                return await redis.ttl(key)
            except Exception as e:
                logger.error(f"Error getting TTL for {key}: {str(e)}")
                return -2  # Key doesn't exist

    @staticmethod
    async def renew_ttl(key: str, ttl: int = DEFAULT_TTL) -> bool:
        """Reset TTL for an existing hash"""
        async with RedisClient.connection() as redis:
            try:
                return await redis.expire(key, ttl)
            except Exception as e:
                logger.error(f"Error renewing TTL for {key}: {str(e)}")
                return False

    # Basic Hash Operations
    @staticmethod
    async def set_hash(key: str, data: Dict[str, Any], ttl: int = DEFAULT_TTL) -> bool:
        """
        Store hash data with automatic TTL.
        
        Sanitizes field values by:
          - Converting booleans to integers (True → 1, False → 0)
          - If the data type is not int, float, or str, using JSON serialization.
        """
        sanitized_data = {}
        for field, value in data.items():
            if isinstance(value, bool):
                sanitized_data[field] = int(value)
            elif isinstance(value, (int, float, str)):
                sanitized_data[field] = value
            else:
                try:
                    sanitized_data[field] = json.dumps(value)
                except Exception as e:
                    logger.error(f"Error serializing field {field} with value {value}: {e}")
                    sanitized_data[field] = str(value)
        async with RedisClient.connection() as redis:
            try:
                await redis.hset(key, mapping=sanitized_data)
                await redis.expire(key, ttl)
                return True
            except Exception as e:
                logger.error(f"Error setting hash {key}: {str(e)}")
                raise

    @staticmethod
    async def get_hash_field(key: str, field: str) -> Optional[Any]:
        """Get single field from hash with boolean conversion."""
        async with RedisClient.connection() as redis:
            try:
                value = await redis.hget(key, field)
                if value is not None:
                    if isinstance(value, bytes):
                        value = value.decode("utf-8")
                    if value == "1":
                        return True
                    elif value == "0":
                        return False
                    return value
            except Exception as e:
                logger.error(f"Error getting field {field} from {key}: {str(e)}")
                return None

    @staticmethod
    async def get_all_hash_fields(key: str) -> Dict[str, Any]:
        """Get all fields from hash with boolean conversion."""
        async with RedisClient.connection() as redis:
            try:
                raw_data = await redis.hgetall(key)
                deserialized_data = {}
                for k, v in raw_data.items():
                    if isinstance(v, bytes):
                        v = v.decode("utf-8")
                    # Convert "1" to True and "0" to False
                    if v == "1":
                        deserialized_data[k] = True
                    elif v == "0":
                        deserialized_data[k] = False
                    else:
                        deserialized_data[k] = v
                return deserialized_data
            except Exception as e:
                logger.error(f"Error getting all fields from {key}: {str(e)}")
                return {}

    @staticmethod
    async def hash_exists(key: str, field: str) -> bool:
        """Check if field exists in hash."""
        async with RedisClient.connection() as redis:
            try:
                return await redis.hexists(key, field)
            except Exception as e:
                logger.error(f"Error checking existence of {field} in {key}: {str(e)}")
                return False

    @staticmethod
    async def delete_hash_field(key: str, field: str) -> int:
        """Delete field from hash."""
        async with RedisClient.connection() as redis:
            try:
                return await redis.hdel(key, field)
            except Exception as e:
                logger.error(f"Error deleting field {field} from {key}: {str(e)}")
                return 0

    ## Advanced Operations
    @staticmethod
    async def update_hash_field(key: str, field: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        """
        Update a single field and renew TTL with boolean conversion.
        
        Converts booleans to integers and applies similar serialization for non-basic types.
        """
        if isinstance(value, bool):
            value = int(value)
        elif not isinstance(value, (int, float, str)):
            try:
                value = json.dumps(value)
            except Exception as e:
                logger.error(f"Error serializing update value for field {field} in {key}: {e}")
                value = str(value)
        async with RedisClient.connection() as redis:
            try:
                await redis.hset(key, field, value)
                await redis.expire(key, ttl)
                return True
            except Exception as e:
                logger.error(f"Error updating field {field} in {key}: {str(e)}")
                return False

    @staticmethod
    async def find_hash_by_field(
        pattern: str, 
        field: str, 
        value: Any
    ) -> Optional[Dict[str, Any]]:
        """Find hash by field value using SCAN
        
        Performs a Redis SCAN operation to find hashes matching both:
        1. Key pattern (Redis glob-style)
        2. Field value match (exact value)
        
        Pattern examples for key matching:
        ┌──────────────┬───────────────────────────────────────────────┐
        │   Pattern    │                 Matches                       │
        ├──────────────┼───────────────────────────────────────────────┤
        │  "user:*"    │ user:1, user:2, user:abc                       │
        │  "order:*-*" │ order:2023-123, order:2024-456                 │
        │  "prod:???"  │ prod:123, prod:abc (exactly 3 chars after :)   │
        └──────────────┴───────────────────────────────────────────────┘

        Args:
            pattern: Redis glob-style pattern for key matching
            field: Hash field name to check
            value: Exact value to match in the specified field

        Returns:
            Dict[str, Any]: First matching hash's full data
            None: If no matches found

        Examples:
            # Find user with exact email match
            user = await find_hash_by_field("user:*", "email", "juan@example.com")
            # Returns: {'name': 'Juan', 'email': 'juan@example.com', ...}

            # Find product by SKU in inventory
            product = await find_hash_by_field("inv:prod*", "sku", "ABC-123")
            # Returns: {'sku': 'ABC-123', 'price': 29.99, ...}

            # Find pending orders with specific status
            order = await find_hash_by_field("order:pending*", "status", "processing")
            # Returns: {'id': 456, 'status': 'processing', ...}

        Notes:
            - SCAN operations are O(N) complexity - use sparingly
            - For frequent queries, maintain a secondary index
            - Field value matching is EXACT (case-sensitive)
            - Returns only the FIRST match found
            - Use for admin tools/debugging, not high-frequency queries
        """
        async with RedisClient.connection() as redis:
            try:
                cursor = b'0'
                while cursor:
                    cursor, keys = await redis.scan(cursor=cursor, match=pattern)
                    for key in keys:
                        if await redis.hexists(key, field):
                            current_value = await redis.hget(key, field)
                            if current_value == value:
                                return await redis.hgetall(key)
                return None
            except Exception as e:
                logger.error(f"Error finding hash by {field}={value}: {str(e)}")
                return None

    # User-specific Methods
    @classmethod
    async def get_user_data(cls, waid: str) -> Dict[str, Any]:
        """Get all user data from hash."""
        return await cls.get_all_hash_fields(f"waid:{waid}")

    @classmethod
    async def update_user_field(cls, waid: str, field: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        """Update a specific user field."""
        return await cls.update_hash_field(f"waid:{waid}", field, value, ttl)

    @classmethod
    async def create_user_record(cls, waid: str, user_data: Dict[str, Any], ttl: int = DEFAULT_TTL) -> bool:
        """Create a new user record with a hash."""
        return await cls.set_hash(f"waid:{waid}", user_data, ttl)

    @classmethod
    async def find_user_by_field(cls, field: str, value: Any) -> Optional[Dict[str, Any]]:
        """Find a user by any field using SCAN."""
        return await cls.find_hash_by_field("waid:*", field, value)
    
    # Handler State Management
    @classmethod
    async def set_handler_state(cls, handler_name: str, user_id: str, state_data: Dict, ttl: int = HANDLER_TTL) -> bool:
        """Store handler state with TTL using a hash."""
        key = f"{handler_name}:{user_id}"
        return await cls.set_hash(key, state_data, ttl)

    @classmethod
    async def get_handler_state(cls, handler_name: str, user_id: str) -> Dict:
        """Get all fields from a handler state hash."""
        key = f"{handler_name}:{user_id}"
        return await cls.get_all_hash_fields(key)

    @classmethod
    async def handler_exists(cls, handler_name: str, user_id: str) -> bool:
        """Check if a handler state exists."""
        key = f"{handler_name}:{user_id}"
        async with RedisClient.connection() as redis:
            return await redis.exists(key) == 1

    @classmethod
    async def delete_handler_state(cls, handler_name: str, user_id: str) -> int:
        """Remove a handler state completely."""
        key = f"{handler_name}:{user_id}"
        return await cls.delete(key)

    @classmethod
    async def create_or_update_handler(cls, handler_name: str, user_id: str, state_data: Dict, ttl: int = HANDLER_TTL) -> Dict:
        """
        Atomically create or update a handler using a hash,
        merging the current state with new data.
        """
        existing = await cls.get_handler_state(handler_name, user_id) or {}
        new_state = {
            **existing,
            **state_data,
            "handler_type": handler_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        await cls.set_handler_state(handler_name, user_id, new_state, ttl)
        return new_state
