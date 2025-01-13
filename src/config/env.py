import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment Configuration
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN")
WP_ACCESS_TOKEN = os.getenv("WP_ACCESS_TOKEN")
WP_PHONE_ID = os.getenv("WP_PHONE_ID")
WP_BID = os.getenv("WP_BID")
API_VERSION = os.getenv("API_VERSION", "v17.0")
PORT = int(os.getenv("PORT", 5000))
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Validation
REQUIRED_ENV_VARS = [
    "WEBHOOK_VERIFY_TOKEN",
    "WP_ACCESS_TOKEN",
    "WP_PHONE_ID",
    "WP_BID",
    "API_VERSION",
    "PORT"
]

for var in REQUIRED_ENV_VARS:
    if not locals()[var]:
        raise EnvironmentError(f"Missing required environment variable: {var}")
