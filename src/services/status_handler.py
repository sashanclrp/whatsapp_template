from utils.logger import logger
from datetime import datetime

class StatusHandler:
    """
    Handles incoming webhook status updates.
    """

    @staticmethod
    async def process_status(data: dict):
        """
        Processes an incoming status webhook.
        :param data: Pre-extracted status data containing status and metadata
        """
        try:
            status = data["status"]
            
            # Required fields
            status_type = status.get('status', 'unknown')
            timestamp = datetime.fromtimestamp(int(status.get('timestamp', 0)))
            
            # Optional fields with safe access
            conversation = status.get('conversation', {}) or {}
            pricing = status.get('pricing', {}) or {}
            
            # Build status message with conditional parts
            status_message = [
                "# Status Update",
                f"Status: {status_type.upper()}",
                f"Message ID: {status.get('id')}",
                f"To: {status.get('recipient_id')}",
                f"Time: {timestamp}"
            ]
            
            # Add optional fields if they exist
            if pricing.get('category'):
                status_message.append(f"Category: {pricing.get('category')}")
            if conversation.get('id'):
                status_message.append(f"Conversation ID: {conversation.get('id')}")
            if conversation.get('expiration_timestamp'):
                expires = datetime.fromtimestamp(int(conversation.get('expiration_timestamp')))
                status_message.append(f"Expires: {expires}")
            
            logger.info("\n                ".join(status_message))
            
            return {"status": "ok"}

        except Exception as e:
            logger.error(f"Error processing status: {str(e)}")
            return {"status": "error", "message": str(e)}