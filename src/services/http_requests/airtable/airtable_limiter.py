import asyncio
import time
from typing import Callable, Any, Dict, Optional


class AirtableRateLimiter:
    """
    A class to ensure that all Airtable requests:
    1) Are processed with concurrency = 1 (only one request at a time).
    2) Are throttled to a maximum of 5 requests/second (200 ms interval).
    """

    def __init__(self, max_requests_per_second: float = 5.0, concurrency_limit: int = 1):
        """
        :param max_requests_per_second: e.g. 5 means 200ms between requests
        :param concurrency_limit: e.g. 1 means only one request at a time
        """
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._min_interval = 1.0 / max_requests_per_second  # e.g. 0.2 seconds
        self._last_request_time = 0.0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Main method to wrap any Airtable call.
        :param func: An async function that performs the actual HTTP request
        :param args, kwargs: The arguments to pass to that function
        :return: The result of the Airtable operation
        """

        # Acquire concurrency lock
        async with self._semaphore:
            # Enforce rate limit: ensure at least _min_interval passes between requests
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)

            # Update last_request_time
            self._last_request_time = time.time()

            # Now actually call the underlying function
            result = await func(*args, **kwargs)

            return result

airtable_limiter = AirtableRateLimiter(
    max_requests_per_second=5,
    concurrency_limit=1
)