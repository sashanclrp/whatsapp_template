import requests
from typing import Optional, Dict, Any
from utils.logger import logger
from ..http_requests.whatsapp_requests import WhatsAppRequests  # Adjust if needed

class WhatsAppServiceSpecial:
    """
    Special WhatsApp messaging functionality:
      - Sending contact cards
      - Sending or requesting location
      (CTA button messages excluded in this class)
    """

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
                    }],
                    "birthday": "YYYY-MM-DD",
                    "emails": [{
                        "email": str,
                        "type": str  # HOME or WORK
                    }],
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
                    }],
                    "urls": [{
                        "url": str,
                        "type": str  # HOME or WORK
                    }]
                }
                
                Only `name.formatted_name` & `phones.phone` are mandatory. All else optional.
                `wa_id` is also optional. If omitted, the message shows "Invite to WhatsApp".
                ContactName should have atleast one optional value be set along with formatted Name
        
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
            response = await WhatsAppRequests.post_request(payload=payload)
            logger.info(f"Contact message sent successfully to {to}")
            return response
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending contact message: {http_err}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending contact message: {err}")
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
            address (str, optional): Location address 
                                     (e.g., "101 Forest Ave, Palo Alto, CA 94301")
        
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

        if name:
            payload["location"]["name"] = name
        if address:
            payload["location"]["address"] = address

        logger.debug(f"Sending location message with payload: {payload}")

        try:
            response = await WhatsAppRequests.post_request(payload=payload)
            logger.info(f"Location message sent successfully to {to}")
            return response
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending location message: {http_err}"
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
            response = await WhatsAppRequests.post_request(payload=payload)
            logger.info(f"Location request message sent successfully to {to}")
            return response
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"HTTP error occurred while sending location request message: {http_err}"
            )
            raise
        except Exception as err:
            logger.error(f"Unexpected error occurred while sending location request message: {err}")
            raise
