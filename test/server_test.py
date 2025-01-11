from fastapi import FastAPI, Request, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import requests
import os
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Environment Variables
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")
WP_ACCESS_TOKEN = os.getenv("WP_ACCESS_TOKEN")
WP_PHONE_ID = os.getenv("WP_PHONE_ID")
WP_BID = os.getenv("WP_BID")
API_VERSION = os.getenv("API_VERSION", "v17.0")
PORT = int(os.getenv("PORT", 5000))

# Initialize FastAPI
app = FastAPI()

# BaseModel for incoming webhook payloads
class WebhookMessage(BaseModel):
    entry: list

# Root Route
@app.get("/")
async def root():
    return {"message": "Nothing to see here. Checkout README.md to start."}


# Webhook Verification Route (GET)
@app.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Forbidden")


# Webhook Event Handling Route (POST)
@app.post("/webhook")
async def handle_webhook(payload: WebhookMessage):
    print("Incoming webhook message:", payload)

    try:
        message = (
            payload.entry[0]["changes"][0]["value"]["messages"][0]
            if payload.entry and payload.entry[0].get("changes")
            else None
        )

        if message and message.get("type") == "text":
            # Send a reply message
            response = requests.post(
                f"https://graph.facebook.com/{API_VERSION}/{WP_PHONE_ID}/messages",
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": message["from"],
                    "text": {"body": "Sashita Says: " + message["text"]["body"]},
                    # "context": {"message_id": message["id"]},
                },
            )
            print("Message Reply Response:", response.status_code, response.text)

            # Mark incoming message as read
            response = requests.post(
                f"https://graph.facebook.com/{API_VERSION}/{WP_PHONE_ID}/messages",
                headers={"Authorization": f"Bearer {WP_ACCESS_TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message["id"],
                },
            )
            print("Message Read Response:", response.status_code, response.text)

    except Exception as e:
        print("Error processing webhook:", e)

    return {"status": "ok"}


# ---------------------------
#    Main entry point
# ---------------------------
if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=5000,
        reload=False  # Disable reload because watch.py handles it
    )