import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

mode = os.getenv("MODE", "PROD")

# MODE CREDENTIALS
if mode == "TEST":
    WP_ACCESS_TOKEN = os.getenv("TEST_WP_ACCESS_TOKEN")
    WP_PHONE_ID = os.getenv("TEST_WP_PHONE_ID")
    WP_BID = os.getenv("TEST_WP_BID")
else:
    WP_ACCESS_TOKEN = os.getenv("WP_ACCESS_TOKEN")
    WP_PHONE_ID = os.getenv("WP_PHONE_ID")
    WP_BID = os.getenv("WP_BID")

# GENERAL CONFIGURATION
API_VERSION = os.getenv("API_VERSION", "v21.0")
PORT = int(os.getenv("PORT", 5000))

BASE_URL = os.getenv("BASE_URL", "https://graph.facebook.com/")
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")

WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")

# TOOLS CREDENTIALS
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
OPENAI_API_KEY = os.getenv("LATTE_OPENAI_API_KEY")

# REDIS CONFIGURATION
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_DB = os.getenv("REDIS_DB", 0)
REDIS_CONNECTION = os.getenv("REDIS_CONNECTION")

# Validation
REQUIRED_ENV_VARS = [
    "WEBHOOK_VERIFY_TOKEN",
    "WP_ACCESS_TOKEN",
    "WP_PHONE_ID",
    "WP_BID",
    "API_VERSION",
    "PORT",
    "BASE_URL",
    "OPENAI_API_KEY",
    "LOG_LEVEL",
    "REDIS_CONNECTION"
]

for var in REQUIRED_ENV_VARS:
    if not locals()[var]:
        raise EnvironmentError(f"Missing required environment variable: {var}")
