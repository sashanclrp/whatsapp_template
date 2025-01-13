from fastapi import APIRouter, Query, Request
from schemas.webhook_schema import WebhookMessage
from controllers.webhook_controller import WebhookController
from utils.logger import logger

# Initialize Router
router = APIRouter()

# Webhook Verification Route (GET)
@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Route for verifying webhook.
    """
    return await WebhookController.verify_webhook(
        hub_mode, hub_verify_token, hub_challenge
    )


# Webhook Event Handling Route (POST)
@router.post("/webhook")
async def handle_webhook(request: Request):
    """
    Route for handling incoming webhook events.
    """
    # Log the raw payload
    raw_payload = await request.json()
    logger.debug(f"Route - Raw webhook payload: {raw_payload}")
    
    try:
        # Parse the payload through our schema
        webhook_message = WebhookMessage.model_validate(raw_payload)
        return await WebhookController.handle_webhook(webhook_message)
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        # Still process the raw payload
        return await WebhookController.handle_webhook(raw_payload)
