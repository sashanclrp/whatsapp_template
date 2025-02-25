from datetime import datetime
from textwrap import dedent
import time

from utils.logger import logger
from utils.redis.redis_handler import RedisHandler
from utils.helper_functions import HelperFunctions

from services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic

from services.http_requests.airtable.airtable_main_db import AirtableLatteDB

class TmpLatteSessions003:
    """
    This class handles the latte sessions 003 template.
    """

    @staticmethod
    async def handle_template(waid: str, message: dict):
        """
        This function sends the latte sessions 003 template.
        """

        pass