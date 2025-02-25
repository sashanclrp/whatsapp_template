from datetime import datetime
import time
import re
from textwrap import dedent
import asyncio

from config.env import OPENAI_API_KEY

from utils.log_handler import IncomingMessageHandler
from utils.logger import logger
from utils.helper_functions import HelperFunctions
from utils.redis.redis_handler import RedisHandler

from services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic
from services.whatsapp_services.handle_media import WhatsAppServiceMedia
from services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from services.whatsapp_services.special_messages import WhatsAppServiceSpecial

from services.http_requests.airtable.airtable_main_db import AirtableLatteDB
from services.http_requests.open_ai_service import OpenAIService

from services.message_handler.symphony_scores.optout_score import OptoutScore
from services.message_handler.symphony_scores.register_score import RegisterScore
from services.message_handler.symphony_scores.join_club_score import JoinClubScore

from services.message_handler.template_handler.template_handler import TemplateHandler

from services.agents.agency import ZomaAgency

class MessageHandler:
    """
    Updated MessageHandler.
    
    All ephemeral flow state is managed using Redis via RedisHandler.
    The previous in-memory dictionaries and get_or_create/remove handler functions are removed.
    """

    # =============================================================================
    # SECTION: Message Processing Core
    # =============================================================================
    @staticmethod
    async def process_message(data: dict) -> dict:
        """
        Processes an incoming webhook message:
          1) Logs the message.
          2) Checks if the user is registered (via Airtable).
          3) If registered, sends a simple greeting or processes opt-out/opt-in.
          4) If not, starts either a registration flow or join-club flow.
        """

        # Extract message and contact data  
        message = data["message"]
        contact = data["contact"]
        waid = message.get("from_") or message.get("from")
        message_id = message.get("id")
        message_type = message.get("type")

        # Log the incoming message
        IncomingMessageHandler.log_incoming_message( 
            contact=contact,
            message=message,
            message_type=message.get("type"),
            interactive_type=message.get("interactive", {}).get("type") if message.get("type") == "interactive" else None
        )

        await WhatsAppServiceBasic.mark_as_read(message_id)

        try:
            # Get user data from Redis or Airtable
            sender_data = await AirtableLatteDB.get_user_data(waid)
            logger.debug(f"{waid} -> Sender Data: {sender_data}")
            is_registered = sender_data is not None

            await WhatsAppServiceBasic.mark_as_read(message_id)

            if is_registered:
                return await MessageHandler._handle_registered_user(
                    waid, message, sender_data, message_type
                )
            else:
                return await MessageHandler._handle_unregistered_user(waid, message)

        except Exception as e:
            logger.error(f"{waid} : Error processing message: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    async def _handle_registered_user(waid: str, message: dict, sender_data: dict, message_type: str) -> dict:
        """Process messages from registered users."""
        user_record_id = sender_data.get("record_id")
        opt_out_status = sender_data.get("opt_out", "opt-in")
        user_first_name = sender_data.get("Nombre", "").split()[0] if sender_data.get("Nombre") else ""
        opt_out_date = sender_data.get("opt_out_last_updated")
        template_status = sender_data.get("template_status")
        template_name = sender_data.get("template_name")
        if opt_out_status == "opt-out":
            return await OptoutScore.handle_optout_score(
                waid, message, user_first_name, user_record_id, opt_out_date
            )
        elif template_status == "locked":
            return await TemplateHandler.handle_templates(waid, message, template_name)
        else:
            return await MessageHandler._handle_active_user(
                waid, message, message_type, sender_data
            )

    @staticmethod
    async def _handle_unregistered_user(waid: str, message: dict) -> dict:
        """Process messages from unregistered users."""
        # Check for existing flows
        if await RedisHandler.handler_exists("register", waid):
            await RegisterScore.handle_user_register_flow(waid, message)
            return {"status": "success", "message": "Registration flow message processed"}
        elif await RedisHandler.handler_exists("join_club", waid):
            await JoinClubScore.handle_join_club(waid, message)
            return {"status": "success", "message": "Join club flow message processed"}
        else:
            # Start new join club flow
            not_registered_text = dedent("""
            bienvenid* a *latte** *sessions*! ☕🎵
            veo que no estás registrad* en *latte CLUB*.
            """).strip()
            await WhatsAppServiceBasic.send_message(to=waid, body=not_registered_text, message_id=message.get("id"))
            
            await RedisHandler.set_handler_state("join_club", waid, {"status": "active"}, 
                                            ttl=RedisHandler.HANDLER_TTL)
            logger.debug(f"{waid} : Set join_club state in Redis")
            await JoinClubScore.send_club_join_menu(waid)
            return {"status": "success", "message": "Join club menu sent"}


    # =============================================================================
    # SECTION: Active User Conversation Handling
    # =============================================================================
    @staticmethod
    async def _handle_active_user(waid: str, message: dict, message_type: str,
                                sender_data: dict) -> dict:
        """Handle messages from active, opted-in users."""

        media_types = ["image", "video", "audio", "document", "sticker"]
        if message_type == "text":
            return await MessageHandler._handle_text_message(waid, message, sender_data)
        elif message_type in media_types:
            pass
        else:
            return await MessageHandler._handle_unsupported_message_type(waid)

    @staticmethod
    async def _handle_text_message(waid: str, message: dict, sender_data: dict) -> dict:
        """Process text messages through Latte Agency."""
        message_text = message.get("text", {}).get("body", "")

        # Call the existing LatteAgency method, passing message_files
        zoma_agent_response = await ZomaAgency.zoma_whatsapp_agency(
            OPENAI_API_KEY,
            user_data=sender_data,
            user_message_text=message_text,
            verbose=False
        )

        logger.debug(f"{waid} : Zoma Agent Response: {zoma_agent_response}")
        await WhatsAppServiceBasic.send_message(to=waid, body=zoma_agent_response['message'])
        return {"status": "success", "message": "Process message completed"}

    @staticmethod
    async def _handle_unsupported_message_type(waid: str) -> dict:
        """Handle unsupported message types."""
        error_msg = "por ahora solo puedo responder a mensajes de texto..."
        await WhatsAppServiceBasic.send_message(to=waid, body=error_msg)
        return {"status": "success", "message": "Unsupported message type handled"}
    