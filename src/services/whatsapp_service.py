import requests
from config.env import WP_ACCESS_TOKEN, WP_PHONE_ID, API_VERSION
from utils.logger import logger
from enum import Enum
from typing import Optional, Union
from pathlib import Path
import mimetypes


class WhatsAppService:
    """
    Service layer responsible for interacting with the WhatsApp Cloud API.
    """

    BASE_URL = f"https://graph.facebook.com/{API_VERSION}/{WP_PHONE_ID}/messages"

    @staticmethod
    async def send_message(to: str, body: str, message_id: str = None):
        """
        Send a WhatsApp message to a user.
        :param to: Recipient's phone number.
        :param body: Text message body.
        :param message_id: (Optional) ID of the message being replied to.
        """
        # Check if the body contains a URL using a simple check for http:// or https://
        has_url = "http://" in body or "https://" in body
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "text": {
                "body": body,
                "preview_url": has_url
            },
        }

        if message_id:
            payload["context"] = {"message_id": message_id}

        logger.debug(f"Sending message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Message sent successfully to {to}")
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending message: {http_err} - Response: {response.text}"
            )
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending message: {err}")

    @staticmethod
    async def mark_as_read(message_id: str):
        """
        Mark a WhatsApp message as read.
        :param message_id: ID of the message to be marked as read.
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Message {message_id} marked as read.")
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred while marking message as read: {http_err}")
        except Exception as err:
            logger.error(f"Unexpected error occurred while marking message as read: {err}")

    @staticmethod
    async def send_buttons_menu(
        to: str,
        body: str,
        buttons: list[dict],
        header: dict = None,
        footer_text: str = None,
    ):
        """
        Send an interactive button menu message via WhatsApp.
        
        Args:
            to (str): Recipient's phone number
            body (str): Main message text (max 1024 chars)
            buttons (list[dict]): List of button objects with 'id' and 'title' keys (max 3 buttons)
            header (dict, optional): Header content. Supported formats:
                - Image header:
                    {
                        "type": "image",
                        "image": {"id": "media_id"}  # or {"link": "url"}
                    }
                - Text header:
                    {
                        "type": "text",
                        "text": "Your text here"
                    }
                - Document header:
                    {
                        "type": "document",
                        "document": {"id": "media_id"}  # or {"link": "url"}
                    }
                - Video header:
                    {
                        "type": "video",
                        "video": {"id": "media_id"}  # or {"link": "url"}
                    }
            footer_text (str, optional): Footer text (max 60 chars)
        
        Raises:
            ValueError: If any input parameters are invalid
            requests.exceptions.HTTPError: If the API request fails
            Exception: For unexpected errors
        """
        # Validate input parameters
        if len(body) > 1024:
            raise ValueError("Body text cannot exceed 1024 characters")
        
        if len(buttons) > 3:
            raise ValueError("Maximum of 3 buttons allowed")
        
        if footer_text and len(footer_text) > 60:
            raise ValueError("Footer text cannot exceed 60 characters")

        # Validate header if provided
        if header:
            valid_header_types = {"text", "image", "video", "document"}
            if header.get("type") not in valid_header_types:
                raise ValueError(f"Header type must be one of {valid_header_types}")
            
            # Validate text header
            if header["type"] == "text" and not header.get("text"):
                raise ValueError("Text header must include 'text' field")
                
            # Validate media headers
            if header["type"] in ["image", "video", "document"]:
                media_obj = header.get(header["type"], {})
                if not media_obj.get("id") and not media_obj.get("link"):
                    raise ValueError(f"{header['type']} header must include either 'id' or 'link'")

        # Construct button objects
        formatted_buttons = []
        for button in buttons:
            if len(button['title']) > 20:
                raise ValueError(f"Button title '{button['title']}' exceeds 20 characters")
            if len(button['id']) > 256:
                raise ValueError(f"Button ID '{button['id']}' exceeds 256 characters")
                
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": button['id'],
                    "title": button['title']
                }
            })

        # Construct payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body
                },
                "action": {
                    "buttons": formatted_buttons
                }
            }
        }

        # Add header if specified
        if header:
            payload["interactive"]["header"] = header

        # Add footer if specified
        if footer_text:
            payload["interactive"]["footer"] = {
                "text": footer_text
            }

        logger.debug(f"Sending interactive message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Interactive message sent successfully to {to}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending interactive message: {http_err} - Response: {response.text}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending interactive message: {err}")
            raise

    @staticmethod
    async def send_list_menu(
        to: str,
        body: str,
        button_text: str,
        sections: list[dict],
        header: Optional[str] = None,
        footer_text: Optional[str] = None,
    ):
        """
        Send an interactive list menu message via WhatsApp.
        
        Args:
            to (str): Recipient's phone number
            body (str): Main message text (max 4096 chars)
            button_text (str): Text for the button that opens the list (max 20 chars)
            sections (list[dict]): List of section objects with format:
                {
                    "title": "Section Title", # max 24 chars
                    "rows": [
                        {
                            "id": "unique_id", # max 200 chars
                            "title": "Row Title", # max 24 chars
                            "description": "Optional description" # max 72 chars
                        },
                        ...
                    ]
                }
            header (str, optional): Header text (max 60 chars)
            footer_text (str, optional): Footer text (max 60 chars)
        
        Raises:
            ValueError: If any input parameters are invalid
            requests.exceptions.HTTPError: If the API request fails
            Exception: For unexpected errors
        """
        # Validate input parameters
        if len(body) > 4096:
            raise ValueError("Body text cannot exceed 4096 characters")
        
        if len(button_text) > 20:
            raise ValueError("Button text cannot exceed 20 characters")
        
        if len(sections) > 10:
            raise ValueError("Maximum of 10 sections allowed")
            
        if header and len(header) > 60:
            raise ValueError("Header text cannot exceed 60 characters")
            
        if footer_text and len(footer_text) > 60:
            raise ValueError("Footer text cannot exceed 60 characters")

        # Validate and format sections
        formatted_sections = []
        for section in sections:
            if len(section['title']) > 24:
                raise ValueError(f"Section title '{section['title']}' exceeds 24 characters")
                
            if len(section['rows']) > 10:
                raise ValueError(f"Section '{section['title']}' has more than 10 rows")
                
            formatted_rows = []
            for row in section['rows']:
                if len(row['id']) > 200:
                    raise ValueError(f"Row ID '{row['id']}' exceeds 200 characters")
                if len(row['title']) > 24:
                    raise ValueError(f"Row title '{row['title']}' exceeds 24 characters")
                if 'description' in row and len(row['description']) > 72:
                    raise ValueError(f"Row description for '{row['title']}' exceeds 72 characters")
                    
                formatted_row = {
                    "id": row['id'],
                    "title": row['title']
                }
                if 'description' in row:
                    formatted_row["description"] = row['description']
                formatted_rows.append(formatted_row)
                
            formatted_sections.append({
                "title": section['title'],
                "rows": formatted_rows
            })

        # Construct payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {
                    "text": body
                },
                "action": {
                    "button": button_text,
                    "sections": formatted_sections
                }
            }
        }

        # Add header if specified
        if header:
            payload["interactive"]["header"] = {
                "type": "text",
                "text": header
            }

        # Add footer if specified
        if footer_text:
            payload["interactive"]["footer"] = {
                "text": footer_text
            }

        logger.debug(f"Sending list menu message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"List menu message sent successfully to {to}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending list menu: {http_err} - Response: {response.text}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending list menu: {err}")
            raise

    class MediaType(Enum):
        """Supported media types for WhatsApp messages"""
        AUDIO = "audio"
        DOCUMENT = "document"
        IMAGE = "image"
        STICKER = "sticker"
        VIDEO = "video"

        @classmethod
        def get_supported_mime_types(cls, media_type: 'WhatsAppService.MediaType') -> set:
            """Returns set of supported MIME types for each media type"""
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
        to: str,
        media_type: MediaType,
        media: Union[str, Path],
        caption: Optional[str] = None,
        filename: Optional[str] = None,
        message_id: Optional[str] = None
    ):
        """
        Send a media message via WhatsApp.
        
        Args:
            to: Recipient's phone number
            media_type: Type of media (audio, document, image, sticker, video)
            media: Either a URL string or a Path object to the media file
            caption: Optional caption for the media (not supported for audio/sticker)
            filename: Optional filename for documents
            message_id: Optional ID of message being replied to
        """
        # Validate media type
        if not isinstance(media_type, WhatsAppService.MediaType):
            raise ValueError(f"Invalid media type. Must be one of: {[t.value for t in WhatsAppService.MediaType]}")

        # Initialize payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type.value,
        }

        # Add reply context if message_id is provided
        if message_id:
            payload["context"] = {"message_id": message_id}

        # Handle URL-based media
        if isinstance(media, str) and (media.startswith('http://') or media.startswith('https://')):
            media_obj = {"link": media}
        
        # Handle file-based media
        else:
            media_path = Path(media)
            if not media_path.exists():
                raise FileNotFoundError(f"Media file not found: {media_path}")

            # Get mime type
            mime_type = mimetypes.guess_type(media_path)[0]
            if not mime_type:
                raise ValueError(f"Could not determine MIME type for file: {media_path}")

            # Validate mime type
            if mime_type not in WhatsAppService.MediaType.get_supported_mime_types(media_type):
                raise ValueError(
                    f"Unsupported MIME type '{mime_type}' for {media_type.value}. "
                    f"Supported types: {WhatsAppService.MediaType.get_supported_mime_types(media_type)}"
                )

            # Upload media file and get media ID
            try:
                # Upload the media file using the upload_media method
                media_id = await WhatsAppService.upload_media(media_path)
                media_obj = {"id": media_id}
            except Exception as e:
                logger.error(f"Failed to upload media file: {e}")
                raise

        # Add caption if supported and provided
        if caption and media_type not in (WhatsAppService.MediaType.AUDIO, WhatsAppService.MediaType.STICKER):
            media_obj["caption"] = caption

        # Add filename for documents
        if media_type == WhatsAppService.MediaType.DOCUMENT and filename:
            media_obj["filename"] = filename

        # Add media object to payload
        payload[media_type.value] = media_obj

        logger.debug(f"Sending media message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Media message sent successfully to {to}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending media message: {http_err} - Response: {response.text}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending media message: {err}")
            raise

    @staticmethod
    async def upload_media(media_path: Union[str, Path]) -> str:
        """
        Upload media to WhatsApp servers and get the media ID.
        Media files are encrypted and persist for 30 days unless deleted earlier.
        
        Args:
            media_path: Path to the media file to upload
        
        Returns:
            str: The media ID returned by WhatsApp
        
        Raises:
            FileNotFoundError: If the media file doesn't exist
            ValueError: If the file type is not supported or file size exceeds limits
            requests.exceptions.HTTPError: If the upload fails
        """
        media_path = Path(media_path)
        if not media_path.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        # Get mime type and validate
        mime_type = mimetypes.guess_type(media_path)[0]
        if not mime_type:
            raise ValueError(f"Could not determine MIME type for file: {media_path}")

        # Check file size limits based on mime type
        file_size = media_path.stat().st_size
        size_limit = None
        
        if mime_type.startswith('audio/') or mime_type.startswith('video/'):
            size_limit = 16 * 1024 * 1024  # 16MB
        elif mime_type.startswith('image/'):
            size_limit = 5 * 1024 * 1024   # 5MB
        elif mime_type == 'image/webp':  # Sticker
            size_limit = 100 * 1024      # 100KB for static stickers
        elif mime_type.startswith('application/') or mime_type == 'text/plain':
            size_limit = 100 * 1024 * 1024  # 100MB

        if size_limit and file_size > size_limit:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds the limit "
                f"({size_limit} bytes) for type {mime_type}"
            )

        # Prepare the upload URL
        upload_url = f"https://graph.facebook.com/{API_VERSION}/{WP_PHONE_ID}/media"

        # Prepare the multipart form data
        with open(media_path, 'rb') as media_file:
            files = {
                'file': (media_path.name, media_file, mime_type)
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'type': mime_type
            }
            
            try:
                response = requests.post(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {WP_ACCESS_TOKEN}"
                    },
                    files=files,
                    data=data
                )
                response.raise_for_status()
                
                result = response.json()
                media_id = result.get('id')
                if not media_id:
                    raise ValueError("No media ID in response")
                    
                logger.info(f"Successfully uploaded media file: {media_path.name} (ID: {media_id})")
                return media_id
                
            except requests.exceptions.HTTPError as http_err:
                logger.error(
                    f"HTTP error occurred while uploading media: {http_err} - Response: {response.text}"
                )
                raise
            except Exception as err:
                logger.error(f"Unexpected error occurred while uploading media: {err}")
                raise
    
    @staticmethod
    async def send_contact_message(to: str, contact: dict):
        """
        Send a contact card message via WhatsApp.
        
        Args:
            to (str): Recipient's phone number
            contact (dict): Contact information with the following structure:
                {
                    "addresses": [{
                        "street": str,
                        "city": str,
                        "state": str,
                        "zip": str,
                        "country": str,
                        "country_code": str,
                        "type": str  # HOME or WORK
                    }], # Additional addresses objects go here, if using multiple addresses
                    "birthday": "YYYY-MM-DD",  # Optional
                    "emails": [{
                        "email": str,
                        "type": str  # HOME or WORK
                    }], # Additional emails objects go here, if using multiple emails
                    "name": {
                        "formatted_name": str,  # Required
                        "first_name": str,
                        "last_name": str,
                        "middle_name": str,
                        "suffix": str,
                        "prefix": str
                    },
                    "org": {
                        "company": str,
                        "department": str,
                        "title": str
                    },
                    "phones": [{
                        "phone": str,
                        "type": str,  # HOME, WORK, CELL, MAIN, IPHONE, or WHATSAPP
                        "wa_id": str
                    }], # Additional phones objects go here, if using multiple phones
                    "urls": [{
                        "url": str,
                        "type": str  # HOME or WORK
                    }] # Additional urls objects go here, if using multiple urls
                }
                
                Note: Only the name.formatted_name & phones.phone fields are mandatory, all other fields are optional.
                Note: wa_id is optional. If omitted, the message will display an Invite to WhatsApp button instead of the standard buttons.
        
        Raises:
            ValueError: If required fields are missing or invalid
            requests.exceptions.HTTPError: If the API request fails
            Exception: For unexpected errors
        """
        # Validate required fields
        if not contact.get("name", {}).get("formatted_name"):
            raise ValueError("Contact must include 'formatted_name' in the name object")

        # Construct payload
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "contacts",
            "contacts": [contact]
        }

        logger.debug(f"Sending contact message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Contact message sent successfully to {to}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending contact message: {http_err} - Response: {response.text}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending contact message: {err}")
            raise

    @staticmethod
    async def send_cta_button(
        to: str,
        body: str,
        button_text: str,
        button_url: str,
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ):
        """
        Send an interactive Call-to-Action URL button message via WhatsApp.
        
        Args:
            to (str): Recipient's phone number
            body (str): Required. Message body text
            button_text (str): Required. Text to display on the button
            button_url (str): Required. URL to load when button is tapped
            header_text (str, optional): Text to display in the header
            footer_text (str, optional): Text to display in the footer
        
        Returns:
            dict: The API response from WhatsApp
            
        Raises:
            ValueError: If required parameters are missing or invalid
            requests.exceptions.HTTPError: If the API request fails
            Exception: For unexpected errors
        """
        # Validate required parameters
        if not all([body, button_text, button_url]):
            raise ValueError("body, button_text, and button_url are required parameters")

        # Validate URL format
        if not (button_url.startswith('http://') or button_url.startswith('https://')):
            raise ValueError("button_url must start with http:// or https://")

        # Construct payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "cta_url",
                "body": {
                    "text": body
                },
                "action": {
                    "name": "cta_url",
                    "parameters": {
                        "display_text": button_text,
                        "url": button_url
                    }
                }
            }
        }

        # Add optional header if provided
        if header_text:
            payload["interactive"]["header"] = {
                "type": "text",
                "text": header_text
            }

        # Add optional footer if provided
        if footer_text:
            payload["interactive"]["footer"] = {
                "text": footer_text
            }

        logger.debug(f"Sending CTA button message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"CTA button message sent successfully to {to}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending CTA button message: {http_err} - Response: {response.text}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending CTA button message: {err}")
            raise

    @staticmethod
    async def send_location(
        to: str,
        latitude: float,
        longitude: float,
        name: Optional[str] = None,
        address: Optional[str] = None
    ):
        """
        Send a location message via WhatsApp.
        
        Args:
            to (str): Required. WhatsApp user phone number
            latitude (float): Required. Location latitude in decimal degrees
            longitude (float): Required. Location longitude in decimal degrees
            name (str, optional): Location name (e.g., "Philz Coffee")
            address (str, optional): Location address (e.g., "101 Forest Ave, Palo Alto, CA 94301")
        
        Returns:
            dict: The API response from WhatsApp
            
        Raises:
            ValueError: If required parameters are missing or invalid
            requests.exceptions.HTTPError: If the API request fails
            Exception: For unexpected errors
        """
        # Validate required parameters
        if not all([to, latitude, longitude]):
            raise ValueError("to, latitude, and longitude are required parameters")

        # Validate latitude range (-90 to 90)
        if not -90 <= float(latitude) <= 90:
            raise ValueError("Latitude must be between -90 and 90 degrees")

        # Validate longitude range (-180 to 180)
        if not -180 <= float(longitude) <= 180:
            raise ValueError("Longitude must be between -180 and 180 degrees")

        # Construct payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "location",
            "location": {
                "latitude": str(latitude),
                "longitude": str(longitude)
            }
        }

        # Add optional fields if provided
        if name:
            payload["location"]["name"] = name
        if address:
            payload["location"]["address"] = address

        logger.debug(f"Sending location message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Location message sent successfully to {to}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending location message: {http_err} - Response: {response.text}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending location message: {err}")
            raise

    @staticmethod
    async def send_request_location(
        to: str,
        body: str,
    ):
        """
        Send a location request message via WhatsApp. This displays a message with a 
        "Send Location" button that allows users to share their location.
        
        Args:
            to (str): Required. WhatsApp user phone number
            body (str): Required. Message text that appears above the location button.
                       Maximum 1024 characters. Can include URLs and formatting.
        
        Returns:
            dict: The API response from WhatsApp
            
        Raises:
            ValueError: If required parameters are missing or invalid
            requests.exceptions.HTTPError: If the API request fails
            Exception: For unexpected errors
        """
        # Validate required parameters
        if not all([to, body]):
            raise ValueError("to and body are required parameters")

        # Validate body length
        if len(body) > 1024:
            raise ValueError("Body text cannot exceed 1024 characters")

        # Construct payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "type": "interactive",
            "to": to,
            "interactive": {
                "type": "location_request_message",
                "body": {
                    "text": body
                },
                "action": {
                    "name": "send_location"
                }
            }
        }

        logger.debug(f"Sending location request message with payload: {payload}")

        try:
            response = requests.post(
                WhatsAppService.BASE_URL,
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"Location request message sent successfully to {to}")
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending location request message: {http_err} - Response: {response.text}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending location request message: {err}")
            raise