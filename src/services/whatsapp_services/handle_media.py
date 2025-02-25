from pathlib import Path
import mimetypes
import base64
from typing import Optional, Union, Dict, Any
from enum import Enum
from utils.logger import logger
import aiohttp

# Import WhatsAppRequests from the http_requests subfolder.
from ..http_requests.whatsapp_requests import WhatsAppRequests
# We need these configuration variables for media upload endpoints.
from config.env import BASE_URL, API_VERSION, WP_PHONE_ID


class WhatsAppServiceMedia:
    """Handles all media-related WhatsApp functionality"""

    class MediaType(Enum):
        """Supported media types for WhatsApp messages"""
        AUDIO = "audio"
        DOCUMENT = "document"
        IMAGE = "image"
        STICKER = "sticker"
        VIDEO = "video"

        @classmethod
        def get_supported_mime_types(cls, media_type: 'WhatsAppServiceMedia.MediaType') -> set:
            """
            Returns set of supported MIME types for each media type.
            """
            SUPPORTED_TYPES = {
                cls.AUDIO: {
                    'audio/aac', 'audio/mp4', 'audio/mpeg', 'audio/amr',
                    'audio/ogg'
                },
                cls.DOCUMENT: {
                    'text/plain', 'application/pdf', 'application/vnd.ms-powerpoint',
                    'application/msword', 'application/vnd.ms-excel',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                },
                cls.IMAGE: {'image/jpeg', 'image/png'},
                cls.STICKER: {'image/webp'},
                cls.VIDEO: {'video/3gp', 'video/mp4'}
            }
            return SUPPORTED_TYPES[media_type]

    @staticmethod
    async def send_media(
        waid: str,
        media_type: 'WhatsAppServiceMedia.MediaType',
        media: Union[str, Path],
        caption: Optional[str] = None,
        filename: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a media message via WhatsApp.

        Args:
            waid: Recipient's phone number.
            media_type: Type of media (audio, document, image, sticker, video).
            media: Either a URL string or a Path object to the local media file.
            caption: Optional caption for the media (not supported for audio and sticker).
            filename: Optional filename (used for documents).
            message_id: Optional message ID for replies.
            
        Returns:
            The WhatsApp API response.
        """
        # Validate media type
        if not isinstance(media_type, WhatsAppServiceMedia.MediaType):
            raise ValueError(
                f"Invalid media type. Must be one of: {[t.value for t in WhatsAppServiceMedia.MediaType]}"
            )

        # Build initial payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": waid,
            "type": media_type.value,
        }

        if message_id:
            payload["context"] = {"message_id": message_id}

        # If media is a URL, use it directly in a link-based object.
        if isinstance(media, str) and (media.startswith('http://') or media.startswith('https://')):
            media_obj = {"link": media}
        else:
            media_path = Path(media)
            if not media_path.exists():
                raise FileNotFoundError(f"Media file not found: {media_path}")

            # Determine and validate MIME type.
            mime_type = mimetypes.guess_type(media_path)[0]
            if not mime_type:
                raise ValueError(f"Could not determine MIME type for file: {media_path}")

            if mime_type not in WhatsAppServiceMedia.MediaType.get_supported_mime_types(media_type):
                raise ValueError(
                    f"Unsupported MIME type '{mime_type}' for {media_type.value}. "
                    f"Supported types: {WhatsAppServiceMedia.MediaType.get_supported_mime_types(media_type)}"
                )

            try:
                # Upload the media file and use the returned media ID.
                media_id = await WhatsAppServiceMedia.upload_media(media_path)
                media_obj = {"id": media_id}
            except Exception as e:
                logger.error(f"Failed to upload media file: {e}")
                raise

        # Add optional caption (if allowed) and filename (for documents).
        if caption and media_type not in (
            WhatsAppServiceMedia.MediaType.AUDIO,
            WhatsAppServiceMedia.MediaType.STICKER
        ):
            media_obj["caption"] = caption

        if media_type == WhatsAppServiceMedia.MediaType.DOCUMENT and filename:
            media_obj["filename"] = filename

        payload[media_type.value] = media_obj

        logger.debug(f"[send_media] waid:{waid} - Sending media message with payload: {payload}")
        try:
            response = await WhatsAppRequests.post_request(payload)
            logger.info(f"[send_media] waid:{waid} - Media message sent successfully")
            return response
        except Exception as err:
            logger.error(f"[send_media] waid:{waid} - Failed to send media message: {err}")
            raise

    @staticmethod
    async def upload_media(media_path: Union[str, Path]) -> str:
        """
        Upload a media file to WhatsApp servers and return the media ID.

        Args:
            media_path: Path to the media file.

        Returns:
            The media ID as returned by WhatsApp.

        Raises:
            FileNotFoundError: If the media file doesn't exist.
            ValueError: If MIME type cannot be determined or file size exceeds allowed limits.
        """
        media_path = Path(media_path)
        if not media_path.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        mime_type = mimetypes.guess_type(media_path)[0]
        if not mime_type:
            raise ValueError(f"Could not determine MIME type for file: {media_path}")

        file_size = media_path.stat().st_size
        size_limit = None
        if mime_type.startswith('audio/') or mime_type.startswith('video/'):
            size_limit = 16 * 1024 * 1024  # 16MB limit.
        elif mime_type.startswith('image/'):
            size_limit = 5 * 1024 * 1024   # 5MB limit.
        elif mime_type == 'image/webp':  # For stickers.
            size_limit = 100 * 1024        # 100KB limit.
        elif mime_type.startswith('application/') or mime_type == 'text/plain':
            size_limit = 100 * 1024 * 1024   # 100MB limit.

        if size_limit and file_size > size_limit:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds the limit ({size_limit} bytes) for type {mime_type}"
            )

        # Read the entire file content.
        with open(media_path, 'rb') as media_file:
            file_content = media_file.read()

        # Prepare the payload for uploading.
        data = {
            'messaging_product': 'whatsapp',
            'type': mime_type
        }

        # Build the proper upload URL. (Note: This endpoint differs from the message endpoint.)
        upload_url = f"{BASE_URL}/{API_VERSION}/{WP_PHONE_ID}/media"

        files = {
            'file': (media_path.name, file_content, mime_type)
        }

        try:
            logger.debug(f"[upload_media] - Uploading media file {media_path.name} to {upload_url}")
            result = await WhatsAppRequests.post_request(
                payload=data,
                custom_url=upload_url,
                files=files
            )
            media_id = result.get('id')
            if not media_id:
                raise ValueError("No media ID in response")
            logger.info(f"[upload_media] - Successfully uploaded {media_path.name} (ID: {media_id})")
            return media_id
        except Exception as err:
            logger.error(f"[upload_media] - Failed to upload {media_path.name}: {err}")
            raise

    @staticmethod
    async def get_media_url(media_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the media URL using its media ID.

        Args:
            media_id: The WhatsApp media ID.

        Returns:
            A dictionary with keys 'url', 'mime_type', and 'file_size' if successful; otherwise None.
        """
        # Build the endpoint. (Trailing slash is important for Graph API requests.)
        endpoint = f"{media_id}/"
        try:
            logger.debug(f"[get_media_url] - Fetching media info for ID: {media_id}")
            result = await WhatsAppRequests.get_request(endpoint=endpoint)
            if not result or 'url' not in result:
                logger.error(f"[get_media_url] - Invalid response for media ID {media_id}: {result}")
                return None
            return {
                'url': result.get('url'),
                'mime_type': result.get('mime_type'),
                'file_size': result.get('file_size'),
            }
        except Exception as e:
            logger.error(f"[get_media_url] - Error getting URL for {media_id}: {str(e)}")
            return None

    @staticmethod
    async def download_media(
        media_id: str, sender_id: str, file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Download WhatsApp media using its media ID and prepare it for further processing.

        Args:
            media_id: The WhatsApp media ID.
            sender_id: Sender ID (used for prefixing the saved filename).
            file_path: Optional base path to save the file. If None, the media is not saved to disk.

        Returns:
            A dictionary with "status" (True/False) and "message".
              - For images, the message contains the base64-encoded image.
              - For other media types, the message contains the raw binary data.
        """
        media_info = await WhatsAppServiceMedia.get_media_url(media_id)
        if not media_info:
            logger.error("Failed to get media URL")
            return {
                "status": False,
                "message": "Failed to get media URL"
            }

        media_url = media_info['url']

        # Maximum allowed sizes by MIME type.
        MAX_SIZES = {
            'audio/aac': 16 * 1024 * 1024,
            'audio/amr': 16 * 1024 * 1024,
            'audio/mpeg': 16 * 1024 * 1024,
            'audio/mp4': 16 * 1024 * 1024,
            'audio/ogg': 16 * 1024 * 1024,
            'text/plain': 100 * 1024 * 1024,
            'application/vnd.ms-excel': 100 * 1024 * 1024,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 100 * 1024 * 1024,
            'application/msword': 100 * 1024 * 1024,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 100 * 1024 * 1024,
            'application/vnd.ms-powerpoint': 100 * 1024 * 1024,
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': 100 * 1024 * 1024,
            'application/pdf': 100 * 1024 * 1024,
            'image/jpeg': 5 * 1024 * 1024,
            'image/png': 5 * 1024 * 1024,
            'image/webp': 500 * 1024,  # For (animated) stickers.
            'video/3gpp': 16 * 1024 * 1024,
            'video/mp4': 16 * 1024 * 1024
        }

        # File extension mapping by MIME type.
        EXTENSION_MAP = {
            'audio/aac': '.aac',
            'audio/amr': '.amr',
            'audio/mpeg': '.mp3',
            'audio/mp4': '.m4a',
            'audio/ogg': '.ogg',
            'text/plain': '.txt',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.ms-powerpoint': '.ppt',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
            'application/pdf': '.pdf',
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'video/3gpp': '.3gp',
            'video/mp4': '.mp4'
        }

        try:
            logger.debug(f"[download_media] - Starting download for media ID: {media_id}")
            # Get the streaming response (returns a (session, response) tuple).
            session, response = await WhatsAppRequests.get_request_stream(media_url)
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"[download_media] - Download failed for {media_id}: {response.status} - {error_text}")
                return {
                    "status": False,
                    "message": f"HTTP error {response.status}"
                }

            # Extract headers and verify content length.
            content_type = response.headers.get('content-type')
            content_length_str = response.headers.get('content-length', '0')
            try:
                content_length = int(content_length_str)
            except ValueError:
                content_length = 0

            if content_type not in EXTENSION_MAP:
                logger.error(f"Unsupported media type: {content_type}")
                return {
                    "status": False,
                    "message": f"Unsupported media type: {content_type}"
                }

            max_size = MAX_SIZES.get(content_type, 0)
            if content_length and content_length > max_size:
                logger.error(
                    f"File size ({content_length} bytes) exceeds maximum allowed size ({max_size} bytes)"
                )
                return {
                    "status": False,
                    "message": "Media file size too big"
                }

            data = bytearray()
            downloaded_size = 0
            async for chunk in response.content.iter_chunked(8192):
                if chunk:
                    downloaded_size += len(chunk)
                    if downloaded_size > max_size:
                        logger.error(
                            f"Download aborted: file size exceeded {max_size} bytes"
                        )
                        return {
                            "status": False,
                            "message": "Media file size too big"
                        }
                    data.extend(chunk)

            # If a file_path is provided, save the downloaded data.
            if file_path:
                extension = EXTENSION_MAP[content_type]
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition and 'filename=' in content_disposition:
                    original_filename = content_disposition.split('filename=')[1].strip('"')
                    filename_final = original_filename
                else:
                    filename_final = f"whatsapp_media_{media_id}{extension}"

                path = Path(file_path)
                final_path = path / f"{sender_id}_{filename_final}"
                final_path.parent.mkdir(parents=True, exist_ok=True)

                with open(final_path, 'wb') as f:
                    f.write(data)

                logger.info(f"[download_media] - Media successfully downloaded to {final_path}")
                logger.debug(f"[download_media] - Media type: {content_type}")
                logger.debug(f"[download_media] - File size: {downloaded_size} bytes")
            else:
                logger.info("[download_media] - No file_path provided. Media downloaded but not saved to disk.")

            # Prepare the response for further processing (e.g., by OpenAI APIs).
            if content_type.startswith('image/'):
                base64_data = base64.b64encode(data).decode('utf-8')
                logger.info(f"[download_media] - Successfully processed image media from {sender_id}")
                return {
                    "status": True,
                    "message": f"data:{content_type};base64,{base64_data}"
                }
            elif content_type.startswith('audio/'):
                logger.info(f"[download_media] - Successfully processed audio media from {sender_id}")
                return {
                    "status": True,
                    "message": data
                }
            elif content_type.startswith(('application/', 'text/')):
                logger.info(f"[download_media] - Successfully processed document from {sender_id}")
                return {
                    "status": True,
                    "message": data
                }
            else:
                logger.info(f"[download_media] - Successfully processed {content_type} media from {sender_id}")
                return {
                    "status": True,
                    "message": data
                }

        except Exception as e:
            error_msg = f"[download_media] - Error downloading {media_id}: {str(e)}"
            logger.error(error_msg)
            return {
                "status": False,
                "message": error_msg
            }

    @staticmethod
    async def delete_media(media_id: str, phone_number_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete media from WhatsApp servers using the media ID.

        Args:
            media_id: The WhatsApp media ID to delete.
            phone_number_id: Optional business phone number ID to verify media ownership.

        Returns:
            A dict containing the status and a message indicating success or failure.
        """
        endpoint = f"{media_id}"
        params = {}
        if phone_number_id:
            params["phone_number_id"] = phone_number_id

        try:
            logger.debug(f"[delete_media] - Attempting to delete media ID: {media_id}")
            result = await WhatsAppRequests.delete_request(endpoint=endpoint, params=params)
            if result.get("success"):
                logger.info(f"[delete_media] - Successfully deleted media ID: {media_id}")
                return {
                    "status": True,
                    "message": "Media deleted"
                }
            else:
                logger.error(f"[delete_media] - Failed to delete {media_id}: {result}")
                return {
                    "status": False,
                    "message": "Deletion failed"
                }
        except Exception as e:
            error_msg = f"[delete_media] - Error deleting {media_id}: {str(e)}"
            logger.error(error_msg)
            return {
                "status": False,
                "message": error_msg
            }
