from datetime import datetime
from textwrap import dedent

from utils.logger import logger
from utils.redis.redis_handler import RedisHandler
from utils.helper_functions import HelperFunctions

from services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic

from services.http_requests.airtable.airtable_main_db import AirtableLatteDB


class OptoutScore:
    """
    This class handles the optout score (flow) for the user.
    """
    
    @staticmethod
    async def handle_optout_score(waid: str, message: dict, user_first_name: str, 
                                 user_record_id: str, opt_out_date: str) -> dict:
        """Process messages from opted-out users."""
        if await RedisHandler.handler_exists("optin", waid):
            state = await RedisHandler.get_handler_state("optin", waid)
            logger.debug(f"{waid} : Found existing opt-in state: {state}")
            await OptoutScore.handle_optin(waid, message)
            return {"status": "success", "message": "Opt-in handler processed"}

        optin_state = {
            "status": "active",
            "user_name": user_first_name,
            "user_record_id": user_record_id,
            "opt_out_date": opt_out_date
        }
        await RedisHandler.set_handler_state("optin", waid, optin_state, 
                                           ttl=RedisHandler.HANDLER_TTL)
        
        await OptoutScore.send_optin_menu(
            waid=waid,
            user_name=user_first_name,
            opt_out_date=optin_state["opt_out_date"]
        )
        logger.debug(f"{waid} : Sent opt-in menu")
        return {"status": "success", "message": "Opt-in menu sent"}
    
    @staticmethod
    async def send_optin_menu(waid: str, user_name: str, opt_out_date: str):
        """
        Sends a buttons menu asking the user if they want to opt back into Latte CLUB.
        """
        logger.debug(f"{waid} -> Sending opt-in menu")
        friendly_date = await HelperFunctions.format_date_friendly(opt_out_date)
        
        message = dedent(f"""
        hola {user_name}, el {friendly_date} decidiste salirte de *latte** *CLUB* y por eso no te hemos vuelto a escribir para invitarte a nuestras actividades.
        
        te gustaría volver a hacer parte del CLUB?
        """).strip()
    
        buttons = [
            {"id": "OPT_IN", "title": "regresar al CLUB"},
            {"id": "KEEP_OUT", "title": "seguir por fuera"}
        ]
    
        await WhatsAppServiceInteractive.send_buttons_menu(
            to=waid,
            body=message,
            buttons=buttons
        )
        logger.debug(f"{waid} -> Sent opt-in button menu")

    @staticmethod
    async def handle_optin(waid: str, message: dict):
        """
        Handle the opt-in flow for a user.
        """
        logger.debug(f"{waid} -> Handling opt-in flow")
        state = await RedisHandler.get_handler_state("optin", waid)
        if not state:
            logger.error(f"{waid} -> User not found in optin state!")
            return
    
        message_type = message.get("type")
        if message_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                button_reply = interactive.get("button_reply", {})
                button_id = button_reply.get("id", "").strip().upper()
                
                if button_id == "OPT_IN":
                    await AirtableLatteDB.update_user_opt_status(waid, "opt-in")

                    # Send confirmation message
                    welcome_back = dedent("""
                    ¡qué alegría tenerte de vuelta! 🎉
                    
                    a partir de ahora volverás a recibir nuestras notificaciones sobre *latte** *sessions* y otras actividades del CLUB. ☕🎵
                    recuerda que puedes escribirnos a cualquier hora, y preguntarnos sobre música o buenos cafés, incluso si no tenemos una *latte** *session* programada.
                    """).strip()
                    await WhatsAppServiceBasic.send_message(to=waid, body=welcome_back)
                    
                elif button_id == "KEEP_OUT":
                    # Send acknowledgment message
                    keep_out_message = dedent("""
                    entendido! respetamos tu decisión.
                    recuerda que puedes volver cuando quieras, solo tienes que escribirnos. ☕
                    """).strip()
                    await WhatsAppServiceBasic.send_message(to=waid, body=keep_out_message)
                
                await RedisHandler.delete_handler_state("optin", waid)
                logger.debug(f"{waid} -> Processed OPT_IN button; sent welcome back message")
        else:
            error_message = "por favor selecciona una de las opciones proporcionadas en el menú ☕"
            await WhatsAppServiceBasic.send_message(to=waid, body=error_message)
            logger.debug(f"{waid} -> Sent error message for opt-in flow (non-interactive)")