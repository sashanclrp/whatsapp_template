from fastapi import HTTPException, Query
from schemas.webhook_schema import WebhookMessage
from services.message_handler import MessageHandler
from services.status_handler import StatusHandler
from config.env import WEBHOOK_VERIFY_TOKEN
from utils.logger import logger


class WebhookController:
    """
    Controller for handling webhook verification and event processing.
    """

    @staticmethod
    async def verify_webhook(
        hub_mode: str = Query(None, alias="hub.mode"),
        hub_verify_token: str = Query(None, alias="hub.verify_token"),
        hub_challenge: str = Query(None, alias="hub.challenge"),
    ):
        """
        Verify the webhook using the verification token.
        """
        if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
            logger.info("Webhook verified successfully!")
            return int(hub_challenge)
        logger.warning("Webhook verification failed.")
        raise HTTPException(status_code=403, detail="Forbidden")

    @staticmethod
    async def handle_webhook(payload: WebhookMessage):
        """
        Handle incoming webhook payloads and delegate to appropriate handler.
        :param payload: Parsed webhook payload (validated via WebhookMessage schema).
        """
        logger.info("Controller - Received webhook payload.")
        try:
            # Extract common fields once
            data = payload.model_dump()
            entry = data.get("entry", [])[0]
            changes = entry.get("changes", [])[0]
            value = changes.get("value", {})

            # Route to appropriate handler based on webhook type
            if value.get("statuses"):
                status_data = {
                    "status": value["statuses"][0],
                    "metadata": value.get("metadata", {})
                }
                await StatusHandler.process_status(status_data)
                return {"status": "ok", "type": "status"}
            
            elif value.get("messages"):
                message_data = {
                    "message": value["messages"][0],
                    "contact": value.get("contacts", [{}])[0],
                    "metadata": value.get("metadata", {})
                }
                
                await MessageHandler.process_message(message_data)
                return {"status": "ok", "type": "message"}
            else:
                logger.warning("Unknown webhook type received")
                return {"status": "unknown_type"}

        except Exception as e:
            logger.error(f"Error processing webhook payload: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")
        return {"status": "ok"}
