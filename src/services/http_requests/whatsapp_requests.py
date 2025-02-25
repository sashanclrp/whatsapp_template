import aiohttp
from datetime import datetime
from config.env import WP_ACCESS_TOKEN, WP_PHONE_ID, API_VERSION, BASE_URL
from utils.logger import logger
from typing import Optional, Dict, Any, Tuple


class WhatsAppRequests:
    """Base class for WhatsApp API requests using aiohttp for asynchronous HTTP calls"""

    # Global shared session, managed via FastAPI startup/shutdown events.
    session: Optional[aiohttp.ClientSession] = None

    # Timestamp of the last API call made.
    last_activity: datetime = None

    @staticmethod
    def get_base_url() -> str:
        """Get the base URL for WhatsApp API requests"""
        return f"{BASE_URL}{API_VERSION}/{WP_PHONE_ID}/messages"

    @staticmethod
    def get_headers() -> Dict[str, str]:
        """Get the default headers for WhatsApp API requests"""
        return {
            "Authorization": f"Bearer {WP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def build_form_data(payload: Dict[str, Any], files: Dict) -> aiohttp.FormData:
        """Helper method to build FormData for multipart/form-data requests."""
        form = aiohttp.FormData()
        if payload:
            for key, value in payload.items():
                form.add_field(key, str(value))
        for key, file_info in files.items():
            if isinstance(file_info, (tuple, list)):
                if len(file_info) == 3:
                    filename, file_content, content_type = file_info
                    form.add_field(key, file_content, filename=filename, content_type=content_type)
                elif len(file_info) == 2:
                    filename, file_content = file_info
                    form.add_field(key, file_content, filename=filename)
                else:
                    form.add_field(key, file_info)
            else:
                form.add_field(key, file_info)
        return form

    @classmethod
    async def post_request(
        cls,
        payload: Dict[str, Any],
        custom_url: Optional[str] = None,
        files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send a POST request to WhatsApp API using a shared aiohttp session if available.
        Minimal logging: one debug message with the response, and error messages on exceptions.
        """
        cls.last_activity = datetime.utcnow()
        url = custom_url or cls.get_base_url()
        response = None
        created_session = False

        # Use the shared session if available; otherwise, create a temporary one.
        if cls.session is None:
            session = aiohttp.ClientSession()
            created_session = True
        else:
            session = cls.session

        try:
            if files:
                data = cls.build_form_data(payload, files)
                json_data = None
            else:
                data = None
                json_data = payload

            async with session.post(
                url,
                headers=cls.get_headers(),
                json=json_data,
                data=data
            ) as response:
                response.raise_for_status()
                response_data = await response.json()
                logger.debug(f"[post_request] - Response: {response_data}")
                return response_data
            

        except aiohttp.ClientResponseError as http_err:
            try:
                error_text = await response.text() if response is not None else "No response"
            except Exception as inner_err:
                error_text = f"Error reading response: {inner_err}"
            logger.error(f"[post_request] - HTTP error occurred: {http_err} - Response: {error_text}")
            raise
        except Exception as err:
            logger.error(f"[post_request] - Unexpected error occurred: {err}")
            raise
        finally:
            if created_session:
                await session.close()

    @classmethod
    async def get_request(
        cls,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a GET request to WhatsApp API using the shared aiohttp session if available.
        """
        cls.last_activity = datetime.utcnow()
        url = f"{BASE_URL}{API_VERSION}/{endpoint}"
        response = None
        created_session = False

        if cls.session is None:
            session = aiohttp.ClientSession()
            created_session = True
        else:
            session = cls.session

        try:
            async with session.get(
                url,
                headers=cls.get_headers(),
                params=params
            ) as response:
                response.raise_for_status()
                response_data = await response.json()
                logger.debug(f"[get_request] - GET request to {url} with params: {params} returned: {response_data}")
                return response_data
        except aiohttp.ClientResponseError as http_err:
            error_text = await response.text() if response is not None else "No response"
            logger.error(f"HTTP error occurred: {http_err} - Response: {error_text}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred: {err}")
            raise
        finally:
            if created_session:
                await session.close()

    @classmethod
    async def delete_request(
        cls,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a DELETE request to WhatsApp API using aiohttp

        Args:
            endpoint: API endpoint
            params: Optional query parameters

        Returns:
            The JSON response as a dictionary.
        """
        cls.last_activity = datetime.utcnow()
        url = f"{BASE_URL}{API_VERSION}/{endpoint}"
        response = None
        created_session = False

        if cls.session is None:
            session = aiohttp.ClientSession()
            created_session = True
        else:
            session = cls.session

        try:
            async with session.delete(
                url,
                headers=cls.get_headers(),
                params=params
            ) as response:
                response.raise_for_status()
                response_data = await response.json()
                logger.debug(f"[delete_request] - DELETE request to {url} with params: {params} returned: {response_data}")
                return response_data
        except aiohttp.ClientResponseError as http_err:
            error_text = await response.text() if response is not None else "No response"
            logger.error(f"HTTP error occurred: {http_err} - Response: {error_text}")
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred: {err}")
            raise
        finally:
            if created_session:
                await session.close()

    @classmethod
    async def get_request_stream(
        cls,
        url: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Tuple[aiohttp.ClientSession, aiohttp.ClientResponse]:
        """
        Perform a streaming GET request using aiohttp, returning the raw ClientResponse object so the caller
        can iterate over the response content. Because streaming requires that the session remain open, this
        method returns a tuple: (session, response). The caller is responsible for closing the session after processing.

        Args:
            url: Full URL to request (e.g., a direct media URL)
            params: Optional query parameters

        Returns:
            Tuple containing:
              - aiohttp.ClientSession: The session used for the request.
              - aiohttp.ClientResponse: The raw response object in stream mode.
        """
        cls.last_activity = datetime.utcnow()
        try:
            if cls.session is None:
                session = aiohttp.ClientSession()
            else:
                session = cls.session
            response = await session.get(
                url,
                headers=cls.get_headers(),
                params=params
            )
            logger.debug(f"[get_request_stream] - Streaming GET request to {url} with params: {params} started. Status: {response.status}, headers: {response.headers}")
            return session, response
        except aiohttp.ClientError as e:
            logger.error(f"[get_request_stream] - Streaming GET request failed: {e}")
            raise
