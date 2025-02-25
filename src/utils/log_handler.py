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
            
            # Set the waid key from recipient_id (see WhatsApp webhook sample structure)
            recipient_waid = status.get('recipient_id', 'unknown-waid')
            
            # Build status message with the waid prefix as our key for debug purposes
            status_message = [
                f"waid: {recipient_waid}",
                "# Status Update",
                f"Status: {status_type.upper()}",
                f"Message ID: {status.get('id')}",
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
            
            logger.info("\n".join(status_message))
            
            return {"status": "ok"}

        except Exception as e:
            logger.error(f"Error processing status for waid: {status.get('recipient_id', 'unknown-waid')}: {str(e)}")
            return {"status": "error", "message": str(e)}
        
class IncomingMessageHandler:
    """
    Handles incoming webhook messages.
    """

    @staticmethod
    def log_incoming_message(contact: dict, message: dict, message_type: str, interactive_type: str = None):
        """
        Logs incoming message details consistently.
        :param contact: Contact information dictionary
        :param message: Message dictionary
        :param message_type: Type of message
        :param interactive_type: Type of interactive message (optional)
        """
        sender_id = message.get("from_") or message.get("from")
        waid_prefix = f"waid: {sender_id}"
        
        if message_type == "text":
            log_message = f"""{waid_prefix}
                # New Message
                From: {contact.get('profile', {}).get('name')} ({sender_id})
                Content: {message.get('text', {}).get('body')}
                Type: {message_type}
                ID: {message.get('id')}
            """
            logger.info(log_message.strip())
        
        elif message_type == "interactive":
            interactive = message.get("interactive", {})
            interactive_type = interactive.get("type")
            
            log_message = f"""{waid_prefix}
                # New Interactive Message
                From: {contact.get('profile', {}).get('name')} ({sender_id})
                Type: {message_type} - {interactive_type}
                ID: {message.get('id')}"""
            logger.info(log_message.strip())

            if interactive_type == "button_reply":
                button_reply = interactive.get("button_reply", {})
                button_id = button_reply.get("id", "").strip().upper()
                button_title = button_reply.get("title", "").strip().lower()
                
                button_log = f"""{waid_prefix}
                    Button Details:
                    ID: {button_id}
                    Title: {button_title}"""
                logger.info(button_log.strip())
            
            elif interactive_type == "list_reply":
                list_reply = interactive.get("list_reply", {})
                selected_id = list_reply.get("id")
                selected_title = list_reply.get("title")
                
                list_log = f"""{waid_prefix}
                    List Reply Details:
                    Raw: {interactive}
                    ID: {selected_id}
                    Title: {selected_title}"""
                logger.info(list_log.strip())
        
        elif message_type in ["image", "video", "audio", "document", "sticker"]:
            media_info = message.get(message_type, {})
            log_message = f"""{waid_prefix}
                # New {message_type.capitalize()} Message
                From: {contact.get('profile', {}).get('name')} ({sender_id})
                Type: {message_type}
                Media ID: {media_info.get('id')}
                Caption: {media_info.get('caption', 'No caption')}
                MIME Type: {media_info.get('mime_type')}
                ID: {message.get('id')}"""
            logger.info(log_message.strip())

        else:
            log_message = f"""{waid_prefix}
                # New {message_type} Message
                From: {contact.get('profile', {}).get('name')} ({sender_id})
                Type: {message_type}
                ID: {message.get('id')}"""
            logger.info(log_message.strip())