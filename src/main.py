import asyncio
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
import uvicorn
import aiohttp
from fastapi.exceptions import RequestValidationError

from routes.webhook_routes import router as webhook_router
from routes.template_routes import router as template_router, custom_validation_exception_handler

from config.env import PORT

from utils.logger import logger
from utils.redis.aioredis import RedisClient

from schemas.global_agent_state import GlobalAgentState

from services.http_requests.whatsapp_requests import WhatsAppRequests
from services.http_requests.airtable.airtable_main_db import AirtableLatteDB
from services.message_handler.symphony_scores.register_score import RegisterScore




# Initialize FastAPI app
app = FastAPI(
    title="WhatsApp Webhook API",
    description="An API for handling WhatsApp Cloud Webhooks",
    version="1.0.0"
)

# Add the custom validation exception handler to the APP instance
app.add_exception_handler(RequestValidationError, custom_validation_exception_handler)

# Include Webhook Routes
app.include_router(webhook_router)

# Include the new template sending router
app.include_router(template_router)


# Root Route
@app.get("/")
async def root():
    """
    Root endpoint.
    """
    return {"message": "Nothing to see here. Checkout README.md to start."}

@app.on_event("startup")
async def startup_event():
    """
    Create a global aiohttp session on startup for efficient reuse,
    and launch a background task to monitor inactivity.
    """
    
    # Create the session with a TCPConnector to limit simultaneous connections.
    connector = aiohttp.TCPConnector(limit=1000, keepalive_timeout=30)
    WhatsAppRequests.session = aiohttp.ClientSession(connector=connector)
    WhatsAppRequests.last_activity = datetime.utcnow()
    logger.info("Global aiohttp session created with TCPConnector limit set to 1000.")
    
    # Schedule the background task that monitors session activity.
    # app.state.session_monitor_task = asyncio.create_task(monitor_session())

    AirtableLatteDB.start_background_tasks()

    # Schedule the registration flow monitor.
    app.state.registration_monitor_task = asyncio.create_task(RegisterScore.monitor_registration_timeouts())

    # Start the latency monitor as a background task
    asyncio.create_task(monitor_loop_latency())
    
    # Initialize Redis connection
    await RedisClient.get_client()
    
    # Store the main event loop in GlobalAgentState and init the thread pool
    GlobalAgentState.loop = asyncio.get_running_loop()
    GlobalAgentState.init()
    
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Properly close the global aiohttp session during shutdown
    and cancel the session monitor task.
    """
    
    if WhatsAppRequests.session:
        await WhatsAppRequests.session.close()
        logger.info("Global aiohttp session closed.")
    if hasattr(app.state, "session_monitor_task"):
        app.state.session_monitor_task.cancel()

async def monitor_session():
    """
    Background task that checks every minute whether the global session has been inactive
    for more than 10 minutes. If so, closes the session.
    """
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute.
            if WhatsAppRequests.session is not None:
                idle_time = datetime.utcnow() - WhatsAppRequests.last_activity
                if idle_time > timedelta(minutes=10):
                    await WhatsAppRequests.session.close()
                    WhatsAppRequests.session = None
                    logger.info("Global aiohttp session closed due to inactivity.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in session monitor: {e}")

@app.get("/redis-test")
async def test_redis():
    """
    Test endpoint for Redis connection
    """
    try:
        async with RedisClient.connection() as redis:
            await redis.set("test", "Test Working Redis")
            value = await redis.get("test")
            return {"status": "success", "value": value}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def monitor_loop_latency():
    """Background task to monitor event loop health"""
    logger.info("Starting event loop latency monitor")
    while True:
        start = time.monotonic()
        await asyncio.sleep(1)
        duration = time.monotonic() - start
        if duration > 1.1:  # 10% latency threshold
            logger.warning(f"Event loop latency: {duration:.3f}s")

# Start the server when executed directly
if __name__ == "__main__":
    logger.info(f"Starting server on port {PORT}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False  # Watchdog handles reloading
    )
