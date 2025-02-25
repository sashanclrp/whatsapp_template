from datetime import datetime
from textwrap import dedent
import time

from utils.logger import logger
from utils.redis.redis_handler import RedisHandler
from utils.helper_functions import HelperFunctions

from services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic

from services.http_requests.airtable.airtable_main_db import AirtableLatteDB

from services.message_handler.template_handler.wp_templates import (
    TmpWelcomeLatteClub, TmpLatteSessions003
)



class TemplateHandler:
    """
    This class handles the template handler for the user.
    """

    @staticmethod
    async def handle_templates(waid: str, message: dict, template_name: str):
        """
        This function handles the template state for the user.
        """
        message_type = message.get("type")

        if message_type == "button":

            button_payload = message.get("button", {}).get("payload", "")
            # =============================================================================
            # SECTION: Handle Opt-Out Button Payload
            # =============================================================================

            if button_payload == "Detener promociones":
                logger.debug(f"[handle_templates] waid:{waid} - template_name:{template_name} - button_payload:{button_payload}")

                opt_out_message = dedent("""
                😢 lamentamos mucho tu partida de *latte** *CLUB*.
                a partir de este momento no nos volveremos a contactar contigo por este medio.
                
                todo esto cumpliendo nuestro política de privacidad y tratamiento de datos que puedes consultar aquí: https://www.lattesessions.com/politica-de-privacidad.
                                            
                recuerda que puedes unirte al CLUB cuando quieras! solo tienes que escribirnos nuevamente. 🎵
                """).strip()
                message_id = message.get("id")
                await WhatsAppServiceBasic.send_message(to=waid, body=opt_out_message, message_id=message_id)
                await AirtableLatteDB.opt_out_user(waid)

                await RedisHandler.update_user_field(waid, "template_status", "", ttl=600)
                await RedisHandler.update_user_field(waid, "template_name", "", ttl=600)
                    
                handler_name = f"tmp_{template_name}"
                await RedisHandler.delete_handler_state(handler_name, waid)
            
            else:
                logger.debug(f"[handle_templates] waid:{waid} - template_name:{template_name} - button_payload:{button_payload}")
                await TemplateHandler.handle_template_state(waid, message, template_name)

        else:
            logger.debug(f"[handle_templates] waid:{waid} - template_name:{template_name} - message_type:{message_type}")
            await TemplateHandler.handle_template_state(waid, message, template_name)
        
    @staticmethod
    async def handle_template_state(waid: str, message: dict, template_name: str):
        """
        This function handles the template reply for the user.
        """
        handler_name = f"tmp_{template_name}"
        if await RedisHandler.handler_exists(handler_name, waid):
            
            if template_name == "welcome_latte_club":
                logger.debug(f"[handle_template_state] waid:{waid} - processing template_name:{template_name}")
                await TmpWelcomeLatteClub.handle_template(waid, message)
                return {"status": "success", "message": "welcome_latte_club template processed"}
            
            elif template_name == "latte_sessions_003":
                logger.debug(f"[handle_template_state] waid:{waid} - processing template_name:{template_name}")
                await TmpLatteSessions003.handle_template(waid, message)
                return {"status": "success", "message": "latte_sessions_003 template processed"}
            


