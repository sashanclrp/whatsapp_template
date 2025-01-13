from fastapi import FastAPI
import uvicorn
from routes.webhook_routes import router as webhook_router
from config.env import PORT
from utils.logger import logger


# Initialize FastAPI app
app = FastAPI(
    title="WhatsApp Webhook API",
    description="An API for handling WhatsApp Cloud Webhooks",
    version="1.0.0"
)

# Include Webhook Routes
app.include_router(webhook_router)

# Root Route
@app.get("/")
async def root():
    """
    Root endpoint.
    """
    return {"message": "Nothing to see here. Checkout README.md to start."}


# Start the server when executed directly
if __name__ == "__main__":
    logger.info(f"Starting server on port {PORT}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False  # Watchdog handles reloading
    )
