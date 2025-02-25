from datetime import datetime
from textwrap import dedent
import time

from utils.logger import logger
from utils.redis.redis_handler import RedisHandler
from utils.helper_functions import HelperFunctions

from services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic

from services.http_requests.airtable.airtable_main_db import AirtableLatteDB


class JoinClubScore:
    """
    This class handles the join club score (flow) for the user.
    """

    @staticmethod
    async def send_club_join_menu(waid: str):
        """
        Sends a buttons menu asking the user if they want to join Latte CLUB.
        :param waid: The ID of the sender.
        """
        message = dedent("""
        te gustaría unirte a *latte CLUB* y ser parte de nuestra comunidad?

        queremos transformar la forma en como vives la música y como vives tus mañanas, con house, café y el mejor ambiente de la ciudad.
                         
        al unirte al CLUB podrás:

        🎥 acceder a  nuestras latte* sessions en los mejores cafés y espacios culturales de la ciudad.
        ☀️ vivir experiencias que conectan la música, la fiesta y una vida saludable.
        🎧 descubre artistas y conoce gente maravillosa.

        ¿qué tal te suena? ☕
        """).strip()

        buttons = [
            {"id": "JOIN_CLUB", "title": "unirme al CLUB"},
            {"id": "NOT_INTERESTED", "title": "no me interesa"}
        ]

        footer_text = "unirse al CLUB es un requisito para interactuar con latte*"

        await WhatsAppServiceInteractive.send_buttons_menu(
            to=waid,
            body=message,
            buttons=buttons,
            header=None,
            footer_text=footer_text
        )


    @staticmethod
    async def handle_join_club(waid: str, message: dict):
        """
        Handle the join club flow for a user.
        """
        message_type = message.get("type")
        if message_type == "interactive":
            interactive = message.get("interactive", {})
            interactive_type = interactive.get("type")
    
            if interactive_type == "button_reply":
                button_reply = interactive.get("button_reply", {})
                button_id = button_reply.get("id", "").strip().upper()
                button_title = button_reply.get("title", "").strip().lower()
    
                await JoinClubScore._handle_join_club_button_reply(button_id, button_title, waid)
        else:
            error_message = "porfavor selecciona alguna de las opciones proporcionadas en el menú ☕"
            await WhatsAppServiceBasic.send_message(to=waid, body=error_message)
    
    @staticmethod
    async def _handle_join_club_button_reply(button_id: str, button_title: str, waid: str):
        """
        Handle the join club flow for a user.
        """
        match button_id:
            case "JOIN_CLUB":
                # Start registration flow by creating registration handler state in Redis
                initial_state = {
                    'step': 'full_name',
                    'last_active': time.time()
                }
                await RedisHandler.set_handler_state("register", waid, initial_state, ttl=RedisHandler.HANDLER_TTL)
    
                response = dedent("""
                genial!
                recuerda que puedes cancelar el registro en cualquier momento escribiendo *LATTEND* en el chat.
                
                para empezar, por favor ingresa tu nombre completo:
                """).strip()
                await WhatsAppServiceBasic.send_message(to=waid, body=response)
                # Remove the join club state since we now moved to registration
                await RedisHandler.delete_handler_state("join_club", waid)
    
            case "NOT_INTERESTED":
                not_intersted_response = dedent("""
                💔
                lamentamos mucho que no estés interesad* en unirte a *latte** *CLUB*.
                                                
                sin embargo, recuerda que puedes unirte cuando quieras! solo tienes que escribirnos nuevamente. 🎵
                                                
                saludos! ☕🎶
                """).strip()
                await WhatsAppServiceBasic.send_message(to=waid, body=not_intersted_response)
                await RedisHandler.delete_handler_state("join_club", waid)