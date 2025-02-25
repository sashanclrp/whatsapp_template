from typing import Optional, List, Dict
from utils.logger import logger
from ..http_requests.whatsapp_requests import WhatsAppRequests
import requests

class WhatsAppServiceInteractive:
    """
    Provides methods for sending interactive WhatsApp messages:
      - Button menus
      - List menus
      - Call-to-Action (CTA) button messages
    """

    @staticmethod
    async def send_buttons_menu(
        to: str,
        body: str,
        buttons: List[Dict],
        header: Dict = None,
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
            # Make the POST request via WhatsAppRequests
            response = await WhatsAppRequests.post_request(payload=payload)
            logger.info(f"Interactive message sent successfully to {to}")
            return response
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending interactive message: {http_err}"
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
        sections: List[Dict],
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
            response = await WhatsAppRequests.post_request(payload=payload)
            logger.info(f"List menu message sent successfully to {to}")
            return response
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending list menu: {http_err}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending list menu: {err}")
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
            response = await WhatsAppRequests.post_request(payload=payload)
            logger.info(f"CTA button message sent successfully to {to}")
            return response
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending CTA button message: {http_err}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending CTA button message: {err}")
            raise