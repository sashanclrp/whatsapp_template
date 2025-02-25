from datetime import datetime
from textwrap import dedent
import time
import asyncio

from utils.logger import logger
from utils.redis.redis_handler import RedisHandler
from utils.helper_functions import HelperFunctions

from services.whatsapp_services.interactive_message import WhatsAppServiceInteractive
from services.whatsapp_services.basic_endpoints import WhatsAppServiceBasic

from services.http_requests.airtable.airtable_main_db import AirtableLatteDB

# Constants specific to registration flow
EMERGENCY_KEYWORDS = ["LATTEND"]
TIMEOUT_FIRST_REMINDER = 60  # 1 minute
TIMEOUT_CANCEL = 120  # 2 minutes
ID_TYPES = ["CC", "CE", "PASAPORTE"]

STEP_MESSAGES = {
    'full_name': "por favor ingresa tu nombre completo:",
    'id_type': "selecciona tu tipo de documento:\n- CC (Cédula de Ciudadanía)\n- CE (Cédula de Extranjería)\n- PASAPORTE",
    'id_number': "ingresa tu número de documento:",
    'birth_date': "ingresa tu fecha de nacimiento (DD/MM/AAAA):",
    'more_about': "¡queremos conocerte mejor!\n\ncuéntanos:\n- 🎶¿qué música te gusta?\n- 🎧¿qué artistas te gustan?\n- 💥¿qué experiencias únicas te gustaría vivir en latte sessions?\n- 🍷¿tienes un gusto particular por alguna bebida?",
    'data_auth': "para terminar porfavor autoriza el tratamiento de tus datos.\n\nsi deseas cancelar tu registro recuerda que puedes escribir 'LATTEND'.\n\npuedes consultar nuestra política de privacidad y tratamiento de datos aquí: https://www.lattesessions.com/politica-de-privacidad.",
}

ID_TYPE_SECTIONS = [{
    "title": "Tipos de Documento",
    "rows": [
        {
            "id": "CC",
            "title": "Cédula de Ciudadanía",
            "description": "Para ciudadanos colombianos"
        },
        {
            "id": "CE",
            "title": "Cédula de Extranjería",
            "description": "Para residentes extranjeros"
        },
        {
            "id": "PASAPORTE",
            "title": "Pasaporte",
            "description": "Para extranjeros"
        }
    ]
}]

class RegisterScore:
    """
    This class handles the register score (flow) for the user.
    """

    @staticmethod
    async def handle_user_register_flow(waid: str, message: dict):
        """
        Handle the registration flow for a user.
        This flow state is stored in Redis under the key "register:{waid}".
        """
        state = await RedisHandler.get_handler_state("register", waid)
        if not state:
            logger.error(f"{waid} -> User not found in registration state!")
            return
    
    
        message_type = message.get("type")
        if message_type == "text":
            message_text = message.get("text", {}).get("body", "")
    
            # Emergency Check
            if message_text.upper() in EMERGENCY_KEYWORDS:
                cancel_message = dedent("""
                uff cancelaste tu registro a *latte** *CLUB*!
                ninguno de tus datos ha sido guardado, ni te conctactaremos por este medio.
                                        
                recuerda que puedes unirte cuando quieras! solo tienes que escribirnos nuevamente. 🎵
                """).strip()
                await WhatsAppServiceBasic.send_message(waid, cancel_message)
                await RedisHandler.delete_handler_state("register", waid)
                return
        else:
            message_text = None
    
        current_time = time.time()
        # Check timeouts based on last active time
        if 'last_active' in state:
            last_active = float(state['last_active']) if 'last_active' in state else current_time
            time_elapsed = current_time - last_active
    
            if time_elapsed > TIMEOUT_CANCEL:
                await WhatsAppServiceBasic.send_message(
                    waid, 
                    "el registro ha sido cancelado por inactividad. por favor, comienza de nuevo."
                )
                await RedisHandler.delete_handler_state("register", waid)
                return
            
            elif time_elapsed > TIMEOUT_FIRST_REMINDER:
                await WhatsAppServiceBasic.send_message(
                    waid,
                    f"¿sigues ahí? estamos esperando tu respuesta para: {STEP_MESSAGES[state['step']]}\n"
                    "el registro se cancelará en 1 minuto si no hay respuesta."
                )
    
        # Update last active time and process current step
        state['last_active'] = current_time
    
        try:
            match state['step']:
                case 'full_name':
                    if not message_text or not message_text.replace(" ", "").isalpha() or len(message_text.split()) < 2:
                        response = "por favor ingresa tu nombre completo (nombres y apellidos, solo letras)."
                    else:
                        state['full_name'] = message_text.title()
                        state['step'] = 'id_type'
                        # Replace the old message with the list menu
                        await WhatsAppServiceInteractive.send_list_menu(
                            to=waid,
                            body="por favor selecciona tu tipo de documento:",
                            button_text="ver opciones",
                            sections= ID_TYPE_SECTIONS
                        )
                        await RedisHandler.set_handler_state("register", waid, state, ttl=RedisHandler.HANDLER_TTL)
                        return  # Return early after sending the menu
    
                case 'id_type':
                    if isinstance(message, dict) and message.get('type') == 'interactive':
                        list_reply = message.get('interactive', {}).get('list_reply', {})
                        selected_id = list_reply.get('id')
                        if selected_id in ID_TYPES:
                            state['id_type'] = selected_id
                            state['step'] = 'id_number'
                            response = STEP_MESSAGES['id_number']
                        else:
                            response = "tipo de documento no válido. Por favor selecciona una opción de la lista."
                    else:
                        response = "por favor selecciona una opción de la lista proporcionada."
    
                case 'id_number':
                    if not message_text or not message_text.strip().isalnum():
                        response = "el número de documento solo puede contener números y letras."
                    else:
                        state['id_number'] = message_text.strip()
                        state['step'] = 'birth_date'
                        response = STEP_MESSAGES['birth_date']
    
                case 'birth_date':
                    try:
                        # Validate date format and age
                        date = datetime.strptime(message_text.strip(), '%d/%m/%Y')
                        if date > datetime.now():
                            raise ValueError("Fecha futura no válida")
                        state['birth_date'] = date.strftime('%Y-%m-%d')
                        state['step'] = 'more_about'
                        response = STEP_MESSAGES['more_about']
                    except ValueError:
                        response = "formato de fecha incorrecto. usa DD/MM/AAAA (ejemplo: 25/12/1990)"
    
                case 'more_about':
                    if not message_text or len(message_text.strip()) < 20:
                        response = "por favor cuéntanos un poco más sobre ti (mínimo 20 caracteres)."
                    else:
                        state['more_about'] = message_text.strip()
                        state['step'] = 'data_auth'
                        
                        # First send the policy message
                        await WhatsAppServiceBasic.send_message(waid, STEP_MESSAGES['data_auth'])
                        
                        # Then send the button menu for data authorization
                        button_message = dedent("""
                        ¿autorizas el uso y tratamiento de tus datos de acuerdo a nuestra política de privacidad y tratamiento de datos?.
                        """).strip()
                        
                        buttons = [
                            {"id": "AUTORIZO", "title": "autorizo"}
                        ]
                        
                        await WhatsAppServiceInteractive.send_buttons_menu(
                            to=waid,
                            body=button_message,
                            buttons=buttons
                        )
                        await RedisHandler.set_handler_state("register", waid, state, ttl=RedisHandler.HANDLER_TTL)
                        return  # Return early after sending messages
    
                case 'data_auth':
                    if message_type == "interactive":
                        interactive = message.get("interactive", {})
                        if interactive.get("type") == "button_reply":
                            button_id = interactive.get("button_reply", {}).get("id")
                            if button_id == "AUTORIZO":
                                state['data_auth'] = True
                                await RedisHandler.set_handler_state("register", waid, state, ttl=RedisHandler.HANDLER_TTL)
                                await RegisterScore.complete_registration(waid)
                                return
                            else:
                                response = "Por favor usa el botón 'autorizo' para finalizar tu registro o escribe 'LATTEND' para cancelar."
                        else:
                            response = "Por favor usa el botón 'autorizo' para finalizar tu registro o escribe 'LATTEND' para cancelar."
                    else:
                        response = "Por favor usa el botón 'autorizo' para finalizar tu registro o escribe 'LATTEND' para cancelar."
    
                case _:
                    response = "Estado no reconocido. Reiniciando registro."
                    await RedisHandler.delete_handler_state("register", waid)
                    return
    
        except Exception as e:
            logger.error(f"{waid} -> Error in registration flow: {str(e)}", exc_info=True)
            response = "Ocurrió un error. Por favor, intenta de nuevo."
            await RedisHandler.delete_handler_state("register", waid)
            return
    
        # Update the registration state in Redis and send response
        await RedisHandler.set_handler_state("register", waid, state, ttl=RedisHandler.HANDLER_TTL)
        await WhatsAppServiceBasic.send_message(waid, response)
    
    # Complete Registration
    @staticmethod
    async def complete_registration(waid: str):
        """
        Completes the registration by saving user data to Airtable,
        deleting the in-Redis state, and sending a confirmation message.
        """
        user_data = await RedisHandler.get_handler_state("register", waid)
        if not user_data:
            logger.error(f"{waid} -> No registration data found during complete_registration")
            return
        await RedisHandler.delete_handler_state("register", waid)
    
        logger.info(f"{waid} -> Registration complete with data: {user_data}")
    
        await AirtableLatteDB.register_user(waid, user_data)
        await asyncio.sleep(5)
    
        completion_message = dedent(f"""
        *¡registro exitoso!* 🎉
        bienvenid* a *latte** *CLUB*, donde esperamos transformar tus mañanas con música, café y buena vibra. ☕🎶

        *estos son tus datos:*
        - nombre: {user_data['full_name']}
        - tipo de documento: {user_data['id_type']}
        - número de documento: {user_data['id_number']}
        - fecha de nacimiento: {user_data['birth_date']}

        *recuerda guardar nuestro contacto en tu whatsapp:*
        - te estaremos escribiendo para informarte sobre nuestros eventos y actividades a {waid}
        - puedes escribirnos a cualquier hora, y preguntarnos sobre música o buenos cafés, incluso si no tenemos una *latte** *session* programada.
        - puedes eliminar tus datos en cualquier momento, es solo cuestión que nos lo hagas saber por este medio.
        """).strip()
        
        await WhatsAppServiceBasic.send_message(waid, completion_message)
        logger.info(f"{waid} -> Sent registration completion message")
        
        return completion_message

    async def monitor_registration_timeouts():
        """
        Background task that every 60 seconds checks all registrations stored in Redis.
        For each registration flow, if the user has been inactive beyond the thresholds,
        it sends a timeout reminder or cancels the registration.
        """
        while True:
            current_time = time.time()
            try:
                # Retrieve all registration keys. Assume keys are stored with prefix "register:".
                register_keys = await RedisHandler.keys("register:*")
                for key in register_keys:
                    # If your keys are like "register:{waid}", you can extract the waid directly:
                    waid = key.split(":", 1)[-1]
                    state = await RedisHandler.get_handler_state("register", waid)
                    if not state:
                        continue

                    last_active = float(state.get("last_active", current_time))
                    time_elapsed = current_time - last_active

                    if time_elapsed > TIMEOUT_CANCEL:
                        # Cancel the flow
                        await WhatsAppServiceBasic.send_message(
                            waid,
                            "el registro ha sido cancelado por inactividad. por favor, comienza de nuevo."
                        )
                        await RedisHandler.delete_handler_state("register", waid)
                        logger.info(f"{waid} -> Registration cancelled due to inactivity")
                    elif time_elapsed > TIMEOUT_FIRST_REMINDER:
                        # Optionally, send reminder
                        step = state.get("step", "tu registro")
                        reminder_message = (
                            f"¿sigues ahí? Estamos esperando tu respuesta para: {step}.\n"
                            "El registro se cancelará en 1 minuto si no hay respuesta."
                        )
                        await WhatsAppServiceBasic.send_message(waid, reminder_message)
                        logger.info(f"{waid} -> Sent inactivity reminder")
                    else:
                        logger.info(f"{waid} -> Registration flow is still active")
                        continue
            except Exception as e:
                logger.error(f"Error in monitor_registration_timeouts: {e}")

            # Pause for 60 seconds before the next scan.
            await asyncio.sleep(60)