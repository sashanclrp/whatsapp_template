
from datetime import datetime
from textwrap import dedent
import time

from utils.logger import logger
from utils.redis.redis_handler import RedisHandler
from utils.helper_functions import HelperFunctions

from services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic

from services.http_requests.airtable.airtable_main_db import AirtableLatteDB

class TmpWelcomeLatteClub:
    """
    This class handles the welcome latte club template.
    """
    
    @staticmethod
    async def handle_template(waid: str, message: dict):
        """
        This function handles the welcome latte club template.
        """
        message_type = message.get("type")
        message_id = message.get("id")
        handler_name = f"tmp_welcome_latte_club"

        if message_type == "button":
            button_payload = message.get("button", {}).get("payload", "")

            if button_payload == "quiero ser parte del CLUB":
                welcome_message = dedent("""
                                
                                    ¡genial! desde ya haces parte de nuestra comunidad!
                                         
                                    *algunas recomendaciones:*
                                        solo vas a poder inscribirte a nuestros eventos cuando te contactemos. 
                                         
                                        este chatbot está integrado con un agente de ia al cual le puedes preguntar sobre nosotros, nuestros artistas, próximos eventos, hasta recomendaciones musicales!
                                        
                                        de igual manera si quieres hablar con alguien del equipo pidele que te comparta los contactos!
                                        
                                        siguiendo nuestra política de privacidad y tratamiento de datos personales (https://www.lattesessions.com/politica-de-privacidad), también puedes preguntarle sobre lo que sabemos de ti! y tranquilo, estos datos no se comparten con nadie ya que la ia está en servidores privados!
                                    
                                        siempre que recibas mensajes de nosotros vas a poder decidir salirte del CLUB!
                                    
                                    *recuerda que cuando se trata de tus datos personales, tu mandas!*
                                """).strip()
                
                await WhatsAppServiceBasic.send_message(to=waid, body=welcome_message, message_id=message_id)
                await RedisHandler.update_user_field(waid, "template_status", "")
                await RedisHandler.update_user_field(waid, "template_name", "")
                await RedisHandler.delete_handler_state(handler_name, waid)
            
        else:
            error_msg = "por favor selecciona una de las opciones proporcionadas en el menú ☕"
            await WhatsAppServiceBasic.send_message(to=waid, body=error_msg, message_id=message_id)

