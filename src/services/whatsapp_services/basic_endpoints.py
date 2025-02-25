from typing import Optional
from ..http_requests.whatsapp_requests import WhatsAppRequests
from utils.logger import logger

class WhatsAppServiceBasic:
    """Basic WhatsApp messaging functionality"""

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
            await WhatsAppRequests.post_request(payload)
            logger.info(f"Message sent successfully to {to}")
        except Exception as err:
            logger.error(f"Failed to send message: {err}")
            raise

    @staticmethod
    async def mark_as_read(message_id: str):
        """Mark a message as read"""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            await WhatsAppRequests.post_request(payload)
            logger.info(f"Message {message_id} marked as read")
        except Exception as err:
            logger.error(f"Failed to mark message as read: {err}")
            raise