from typing import Optional, List, Dict
from ..http_requests.whatsapp_requests import WhatsAppRequests
from utils.logger import logger
class WhatsAppServiceTemplates:
    """
    Provides methods for sending WhatsApp templates.
    """

    @staticmethod
    async def text_template(
        phone_number: str,
        template_name: str,
        parameters: Optional[List[Dict[str, str]]] = None,
        language_code: str = "es"
    ) -> Dict:
        """
        Send a text-only WhatsApp template message.

        Args:
            phone_number (str): The recipient's phone number
            template_name (str): Name of the template to send
            parameters (Optional[List[Dict[str, str]]]): List of parameters for the template.
                Each parameter should be a dict with keys:
                - type: The parameter type (text)
                - parameter_name: Name of the parameter
                - text: The text value
            language_code (str): Language code for the template. Defaults to "es"

        Returns:
            Dict: Response from the WhatsApp API
        """
        template_data = {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }

        if parameters:
            template_data["components"] = [
                {
                    "type": "body",
                    "parameters": parameters
                }
            ]

        data = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": template_data
        }

        return await WhatsAppRequests.post_request(data)

    @staticmethod
    async def media_template(
        phone_number: str,
        template_name: str,
        media_type: str,  # 'image', 'video', 'document'
        media_id: Optional[str] = None,
        media_url: Optional[str] = None,
        body_parameters: Optional[List[Dict]] = None,
        language_code: str = "es"
    ) -> Dict:
        """
        Send a WhatsApp template message with media (image, video, or document).

        Args:
            phone_number (str): The recipient's phone number
            template_name (str): Name of the template to send
            parameters (Optional[List[Dict[str, str]]]): List of parameters for the template.
                Each parameter should be a dict with keys:
                - type: The parameter type (text)
                - parameter_name: Name of the parameter
                - text: The text value
            media_id (Optional[str]): ID of the pre-uploaded media
            media_url (Optional[str]): URL of the media to be sent
            language_code (str): Language code for the template. Defaults to "es"

        Returns:
            Dict: Response from the WhatsApp API

        Raises:
            ValueError: If both media_id and media_url are provided or if neither is provided
        """
        if (media_id and media_url) or (not media_id and not media_url):
            raise ValueError("Either media_id or media_url must be provided, but not both")

        header_component = {
            "type": "header",
            "parameters": [
                {
                    "type": media_type,
                    media_type: {
                        "id": media_id
                    } if media_id else {"link": media_url}
                }
            ]
        }

        components = [header_component]

        if body_parameters:
            components.append({
                "type": "body",
                "parameters": body_parameters
            })

        template_data = {
            "name": template_name,
            "language": {"code": language_code},
            "components": components
        }

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "template",
            "template": template_data
        }

        logger.debug(f"[send_media_template] waid:{phone_number} - Sending template: {data}")

        return await WhatsAppRequests.post_request(data)

    @staticmethod
    async def location_template(
        phone_number: str,
        template_name: str,
        latitude: str,
        longitude: str,
        name: str,
        address: str,
        body_parameters: Optional[List[Dict]] = None,
        language_code: str = "es"
    ) -> Dict:
        """
        Send a location-based WhatsApp template message with map preview.
        
        Required components per WhatsApp's API:
        - Header: Location coordinates with name and address
        - Optional Body: Text parameters for template message

        Args:
            phone_number (str): Recipient's phone number in E.164 format
            template_name (str): Approved template name
            latitude (str): Latitude coordinate as string (e.g., "37.483307")
            longitude (str): Longitude coordinate as string (e.g., "-122.148981")
            name (str): Name of the location (e.g., "Main Store")
            address (str): Physical address of the location
            body_parameters (Optional[List[Dict]]): Body parameters for template text replacement.
                Each parameter should be a dict with keys:
                - type: "text" (other types require different template methods)
                - text: Replacement text
            language_code (str): BCP-47 language code. Default: "es"

        Returns:
            Dict: WhatsApp API response containing:
                - messaging_product: "whatsapp"
                - contacts: [{"input": phone_number, "wa_id": WhatsApp ID}]
                - messages: [{"id": message_id}]

        Raises:
            ValueError: If required location parameters are missing
            HTTPException: For API request failures (handled in WhatsAppRequests)

        Example:
            send_location_template(
                phone_number="1234567890",
                template_name="store_location",
                latitude="37.483307",
                longitude="-122.148981",
                name="Main Store",
                address="123 Business Rd",
                body_parameters=[{"type": "text", "text": "Open 9-5"}]
            )
        """
        location_param = {
            "type": "location",
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "name": name,
                "address": address
            }
        }

        header_component = {
            "type": "header",
            "parameters": [location_param]
        }

        components = [header_component]

        if body_parameters:
            components.append({
                "type": "body",
                "parameters": body_parameters
            })

        template_data = {
            "name": template_name,
            "language": {"code": language_code},
            "components": components
        }

        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "template",
            "template": template_data
        }

        return await WhatsAppRequests.post_request(data)
