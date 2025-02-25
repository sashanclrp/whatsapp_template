from redis.asyncio import Redis
from contextlib import asynccontextmanager
from config.env import REDIS_CONNECTION, REDIS_HOST, REDIS_PORT, REDIS_DB
from typing import Optional, AsyncIterator
from utils.logger import logger

class RedisClient:
    _instance: Optional[Redis] = None
    
    @classmethod
    async def get_client(cls) -> Redis:
        """Get the singleton Redis client instance"""
        if cls._instance is None:
            if REDIS_CONNECTION != "None":
                redis_url = REDIS_CONNECTION
            else:
                redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
            
            cls._instance = Redis.from_url(
                redis_url,
                decode_responses=True,
                encoding="utf-8"
            )
            logger.info(f"Redis connection established to {redis_url}")
        else:
            # Instead of checking a nonexistent 'closed' attribute,
            # try pinging the Redis server to ensure the connection is alive.
            try:
                await cls._instance.ping()
            except Exception as exc:
                logger.warning(f"Redis ping failed: {exc}. Reinitializing client.")
                if REDIS_CONNECTION != "None":
                    redis_url = REDIS_CONNECTION
                else:
                    redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
                cls._instance = Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    encoding="utf-8"
                )
                logger.info(f"Redis connection re-established to {redis_url}")
        return cls._instance

    @classmethod
    @asynccontextmanager
    async def connection(cls) -> AsyncIterator[Redis]:
        """Async context manager for Redis operations"""
        client = await cls.get_client()
        try:
            yield client
        except Exception as e:
            logger.error(f"Redis operation failed: {str(e)}")
            raise
        finally:
            # Connection managed by singleton, don't close here
            pass

# Initialize connection on startup
async def init_redis():
    await RedisClient.get_client()