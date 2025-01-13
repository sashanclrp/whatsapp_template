from services.whatsapp_service import WhatsAppService
from services.airtable_service import AirtableService
from services.open_ai_service import OpenAIService
from utils.logger import logger
from datetime import datetime
import time
import re
from textwrap import dedent


class MessageHandler:
    """
    Handles incoming webhook messages and delegates actions to WhatsAppService.
    """

    # Class-level dictionary to store handler instances per user
    _handlers = {}
    _openai_conversations = {}

    def __init__(self):
        self.appointment_state = {}
        self.ai_conversation = {}
        logger.debug(f"New MessageHandler instance created with empty state: {self.appointment_state}")

    @classmethod
    def get_or_create_handler(cls, sender_id: str) -> 'MessageHandler':
        """Get existing handler or create new one for a user"""
        if sender_id not in cls._handlers:
            logger.debug(f"Creating new handler for user {sender_id}")
            cls._handlers[sender_id] = cls()
        return cls._handlers[sender_id]

    @classmethod
    def remove_handler(cls, sender_id: str):
        """Remove handler when flow is complete or times out"""
        if sender_id in cls._handlers:
            logger.debug(f"Removing handler for user {sender_id}")
            del cls._handlers[sender_id]

    @classmethod
    def get_or_create_openai_conversation(cls, sender_id: str) -> 'MessageHandler':
        if sender_id not in cls._openai_conversations:
            cls._openai_conversations[sender_id] = cls()
        return cls._openai_conversations[sender_id]

    @classmethod
    def remove_openai_conversation(cls, sender_id: str):
        if sender_id in cls._openai_conversations:
            del cls._openai_conversations[sender_id]

    @staticmethod
    def _log_incoming_message(contact: dict, message: dict, message_type: str, interactive_type: str = None):
        """
        Logs incoming message details consistently.
        :param contact: Contact information dictionary
        :param message: Message dictionary
        :param message_type: Type of message
        :param interactive_type: Type of interactive message (optional)
        """
        sender_id = message.get("from_") or message.get("from")
        
        if message_type == "text":
            logger.info(f"""
                # New Message
                From: {contact.get('profile', {}).get('name')} ({sender_id})
                Content: {message.get('text', {}).get('body')}
                Type: {message_type}
                ID: {message.get('id')}
            """.strip())
        elif message_type == "interactive":
            interactive = message.get("interactive", {})
            interactive_type = interactive.get("type")
            
            logger.info(f"""
                    # New Interactive Message
                    From: {contact.get('profile', {}).get('name')} ({sender_id})
                    Type: {message_type} - {interactive_type}
                    ID: {message.get('id')}
            """.strip())

            if interactive_type == "button_reply":
                    button_reply = interactive.get("button_reply", {})
                    button_id = button_reply.get("id", "").strip().upper()
                    button_title = button_reply.get("title", "").strip().lower()
                    
                    logger.info(f"""
                            Button Details:
                            ID: {button_id}
                            Title: {button_title}
                    """.strip())
            
            elif interactive_type == "list_reply":
                list_reply = interactive.get("list_reply", {})
                selected_id = list_reply.get("id")
                selected_title = list_reply.get("title")
                
                logger.info(f"""
                        List Reply Details:
                        Raw: {interactive}
                        ID: {selected_id}
                        Title: {selected_title}
                """.strip())

        else:
            logger.info(f"""
                # New {message_type} Message
                From: {contact.get('profile', {}).get('name')} ({sender_id})
                Type: {message_type}
                ID: {message.get('id')}
            """.strip())

    @staticmethod
    async def process_message(data: dict):
        """
        Processes an incoming webhook message.
        :param data: Pre-extracted message data containing message, contact, and metadata
        """
        try:
            message = data["message"]
            contact = data["contact"]
            
            # Log the incoming message
            MessageHandler._log_incoming_message(
                contact=contact,
                message=message,
                message_type=message.get("type"),
                interactive_type=message.get("interactive", {}).get("type") if message.get("type") == "interactive" else None
            )
            
            # Get sender ID from either from_ or from
            sender_id = message.get("from_") or message.get("from")
            message_id = message.get("id")
            message_type = message.get("type")
            sender_data = await AirtableService.get_registered_user(sender_id)
            sender_registerd = sender_data is not None
            
            # If user is registered, send a welcome message
            if sender_registerd:
                user_first_name = sender_data[0].get("Nombre").split(" ")[0]
                message = f"Hola {user_first_name} bienvenid@ a Latte Sessions!" + "\n" + "¿Como puedo ayudarte?"
                await WhatsAppService.send_message(to=sender_id, body=message)
                await WhatsAppService.mark_as_read(message_id)
                return {"status": "success", "message": "Welcome message sent"}

            # If user has an active handler, process through registration flow
            elif sender_id in MessageHandler._handlers:
                handler = MessageHandler._handlers[sender_id]
                logger.debug(f"Found existing handler for {sender_id}. State: {handler.appointment_state}")
               
             
                await handler.handle_user_register_flow(sender_id, message)
               
                return {"status": "success", "message": "Registration flow message processed"}
            
            # If user has an active openai conversation, process through ai conversation
            elif sender_id in MessageHandler._openai_conversations:
                conversation = MessageHandler._openai_conversations[sender_id]
                logger.debug(f"Found existing openai conversation for {sender_id}. State: {conversation.ai_conversation}")
                await WhatsAppService.mark_as_read(message.get("id"))
                await conversation.handle_ai_conversation(sender_id, message)

                logger.info(f"""
                    # Current AI Conversation
                    Sender ID: {sender_id}  
                    Conversation State: {conversation.ai_conversation}
                    Messages: {conversation.ai_conversation[sender_id]["messages"]}
                """.strip())
                
                return {"status": "success", "message": "AI conversation message processed"}
            
            # Handle regular messages
            elif message_type == "text":
                return await MessageHandler._handle_text_message(message, contact)
            
            elif message_type == "interactive":
                interactive = message.get("interactive", {})
                interactive_type = interactive.get("type")
                
                if interactive_type == "button_reply":
                    button_reply = interactive.get("button_reply", {})
                    button_id = button_reply.get("id", "").strip().upper()
                    button_title = button_reply.get("title", "").strip().lower()

                    await MessageHandler._handle_menu_option(button_id, button_title, sender_id, message_id)
                    
                    return {"status": "success", "message": "Button reply processed"}
            else:
                logger.warning(f"Unsupported message type: {message_type}")
                return {"status": "error", "message": f"Unsupported message type: {message_type}"}

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    @staticmethod
    async def _handle_text_message(message: dict, contact: dict):
        """
        Handles a text message.
        :param message: The text message.
        """
        text_body = message.get("text", {}).get("body", "")
        sender_id = message.get("from_") or message.get("from")  # Try both fields

        if MessageHandler.is_greeting(text_body.lower().strip()):
            # await MessageHandler.send_welcome_message(sender_id, message.get('id'), contact)
            await MessageHandler.send_welcome_menu(sender_id, contact)
        elif text_body.lower().strip() == "sashacontact":
            contact_info = {
                "addresses": [
                    {
                    "street": "1 Lucky Shrub Way",
                    "city": "Menlo Park",
                    "state": "CA",
                    "zip": "94025",
                    "country": "United States",
                    "country_code": "US",
                    "type": "Office"
                    },
                    {
                    "street": "1 Hacker Way",
                    "city": "Menlo Park",
                    "state": "CA",
                    "zip": "94025",
                    "country": "United States",
                    "country_code": "US",
                    "type": "Pop-Up"
                    }
                ],
                "birthday": "1999-01-23",
                "emails": [
                    {
                    "email": "bjohnson@luckyshrub.com",
                    "type": "Work"
                    },
                    {
                    "email": "bjohnson@luckyshrubplants.com",
                    "type": "Work (old)"
                    }
                ],
                "name": {
                    "formatted_name": "Barbara J. Johnson",
                    "first_name": "Barbara",
                    "last_name": "Johnson",
                    "middle_name": "Joana",
                    "suffix": "Esq.",
                    "prefix": "Dr."
                },
                "org": {
                    "company": "Lucky Shrub",
                    "department": "Legal",
                    "title": "Lead Counsel"
                },
                "phones": [
                    {
                    "phone": "+16505559999",
                    "type": "Landline"
                    },
                    {
                    "phone": "+573168227670",
                    "type": "Mobile",
                    "wa_id": "573168227670"
                    }
                ],
                "urls": [
                    {
                    "url": "https://www.luckyshrub.com",
                    "type": "Company"
                    },
                    {
                    "url": "https://www.facebook.com/luckyshrubplants",
                    "type": "Company (FB)"
                    }
                ]
            }
            await WhatsAppService.send_contact_message(sender_id, contact_info)
        else:
            # Send reply
            await WhatsAppService.send_message(
                to=sender_id,
                body=f"Sashita Says: {text_body}",
                message_id=message['id']
            )
            
        if not text_body or not sender_id:
            logger.error("Missing required fields in text message")
            return

        logger.info(f"Processing text message from {sender_id}: {text_body}")

        # Mark as read
        await WhatsAppService.mark_as_read(message['id'])

    @staticmethod
    def is_greeting(message: str) -> bool:
        """
        Checks if the message is a greeting.
        :param message: The message to check.

        returns: bool
        """
        greetings = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "hola", "buenos dias", "buenos tardes", "buenos noches"]
        return any(greeting in message.lower() for greeting in greetings)

    @staticmethod
    def get_sender_name(contact: dict) -> str:
        """
        Gets the sender's name from the contact.
        :param contact: The contact.

        returns: str
        """
        sender_name = contact.get("profile", {}).get("name") or contact.get("wa_id") or ""
        return sender_name

    @staticmethod
    async def send_welcome_message(sender_id: str, message_id: str, contact: dict):
        """
        Sends a welcome message to the user.
        :param sender_id: The ID of the sender.
        :param message_id: The ID of the message.
        """
        sender_name = MessageHandler.get_sender_name(contact)
        first_name = sender_name.split(" ")[0]
        message = f"Hola {first_name} bienvenido a Latte Sessions!" + "\n" + "¿Como puedo ayudarte?"
        await WhatsAppService.send_message(to=sender_id, body=message, message_id=message_id)

    @staticmethod
    async def send_welcome_menu(sender_id: str, contact: dict):
        """
        Sends a buttons menu to the user.
        :param sender_id: The ID of the sender.
        """
        sender_name = MessageHandler.get_sender_name(contact)
        first_name = sender_name.split(" ")[0]
        message = f"Hola {first_name} bienvenid@ a Latte Sessions!" + "\n" + "¿Como puedo ayudarte?"
        buttons = [ 
            {"id": "REGISTER", "title": "Registrarme"}, 
            {"id": "SESSIONS", "title": "Next Latte Session"}, 
            {"id": "LATTE_AI", "title": "LatteAI"} 
        ]
        footer_text = "Selecciona una opción"

        await WhatsAppService.send_buttons_menu(
            to=sender_id,
            body=message,
            buttons=buttons,
            header=None,
            footer_text=footer_text,
        )

    @staticmethod
    async def _handle_menu_option(button_id: str, button_title: str, sender_id: str, message_id: str):
        """
        Handles a menu option.
        :param button_id: The ID of the button.
        :param button_title: The title of the button.
        :param sender_id: The ID of the sender.
        """
        # Mark as read
        await WhatsAppService.mark_as_read(message_id)

        match button_id:
            case "REGISTER":
                # Get or create handler instance for this user
                handler = MessageHandler.get_or_create_handler(sender_id)
                
                # Initialize registration state
                handler.appointment_state[sender_id] = {
                    'step': 'full_name',
                    'last_active': time.time()
                }
                
                logger.debug(f"""
                    After REGISTER State Update:
                    Sender ID: {sender_id}
                    Handler State: {handler.appointment_state}
                    Active Handlers: {list(MessageHandler._handlers.keys())}
                """.strip())

                response = "Por favor ingresa tu nombre completo:"
                await WhatsAppService.send_message(to=sender_id, body=response)
            
            case "SESSIONS":
                response = "flujo de next latte session"
                await WhatsAppService.send_media(
                    to=sender_id,
                    media_type=WhatsAppService.MediaType.DOCUMENT,
                    media="/mnt/c/Users/Lenovo/Downloads/141153441343.pdf",
                    caption=response,
                    filename="Davivienda.pdf",
                    message_id=None
                )
            case "LATTE_AI":
                conversation = MessageHandler.get_or_create_openai_conversation(sender_id)
                conversation.ai_conversation[sender_id] = {
                    "status": "active",
                    "messages": []
                }
                response_1 = "Acabas de iniciar una conversación con LatteAI, cuando desees terminarla escribe *'LATTEND'*"
                response_2 = "Hola, soy LatteAI, puedes preguntarme sobre nuestras próximas sesiones, nuestras grabaciones en Youtube, etc...\nComo puedo ayudarte?"
                
                logger.debug(f"""
                    After LATTE_AI Update:
                    Sender ID: {sender_id}
                    LatteAI State: {conversation.ai_conversation}
                    Active Conversations: {list(MessageHandler._openai_conversations.keys())}
                """.strip())
                
                await WhatsAppService.send_message(to=sender_id, body=response_1)
                await WhatsAppService.send_message(to=sender_id, body=response_2)

            case _:
                response = "opcion no valida"
                await WhatsAppService.send_message(to=sender_id, body=response)

    async def handle_user_register_flow(self, to: str, message: dict):
        """
        Handle the registration flow for a user.
        """
        
        if to not in self.appointment_state:
            logger.error(f"User {to} not found in registration state!")
            return

        state = self.appointment_state[to]
        step = state['step']

                # Constants specific to registration flow
        EMERGENCY_KEYWORDS = ["CODA", "EXIT", "CANCEL"]
        TIMEOUT_FIRST_REMINDER = 60  # 1 minute
        TIMEOUT_CANCEL = 120  # 2 minutes
        ID_TYPES = ["CC", "CE", "PASAPORTE"]
        
        STEP_MESSAGES = {
            'full_name': "Por favor ingresa tu nombre completo:",
            'id_type': "Selecciona tu tipo de documento:\n- CC (Cédula de Ciudadanía)\n- CE (Cédula de Extranjería)\n- PASAPORTE",
            'id_number': "Ingresa tu número de documento:",
            'birth_date': "Ingresa tu fecha de nacimiento (DD/MM/AAAA):",
            'more_about': "¡Queremos conocerte mejor!\n\nCuéntanos:\n- ¿Qué música te gusta?\n- ¿Qué experiencias únicas te gustaría vivir en Latte Sessions?\n- ¿Tienes un gusto particular por alguna bebida?",
            'data_auth': "¿Autorizas el uso y tratamiento de tus datos de acuerdo a nuestra Política de Privacidad y Tratamiento de Datos?\n\nPuedes consultar la política aquí: https://candyflip.notion.site/Pol-tica-de-Privacidad-y-Tratamiento-de-Datos-abc1ecae9c404af1abbed257c36034e3\n\nResponde 'SI' para aceptar.",
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

        message_type = message.get("type")
        if message_type == "text":
            message_text = message.get("text", {}).get("body", "")

            # Emergency Check
            if message_text.upper() in EMERGENCY_KEYWORDS:
                self.appointment_state.pop(to, None)
                await WhatsAppService.send_message(to, "El registro ha sido cancelado. ¡Gracias!")
                return
        else:
            message_text = None

        # Get current state or initialize new one
        current_time = time.time()
        state = self.appointment_state.get(to, {
            'step': 'full_name',
            'last_active': current_time
        })

        # Check timeouts
        if 'last_active' in state:
            time_elapsed = current_time - state['last_active']
            
            if time_elapsed > TIMEOUT_CANCEL:
                self.appointment_state.pop(to, None)
                await WhatsAppService.send_message(
                    to, 
                    "El registro ha sido cancelado por inactividad. Por favor, comienza de nuevo."
                )
                return
            
            elif time_elapsed > TIMEOUT_FIRST_REMINDER:
                await WhatsAppService.send_message(
                    to,
                    f"¿Sigues ahí? Estamos esperando tu respuesta para: {STEP_MESSAGES[state['step']]}\n"
                    "El registro se cancelará en 1 minuto si no hay respuesta."
                )

        # Update last active time
        state['last_active'] = current_time
        step = state.get('step')

        # Process steps with validation
        try:
            match step:
                case 'full_name':
                    if not message_text.replace(" ", "").isalpha() or len(message_text.split()) < 2:
                        response = "Por favor ingresa tu nombre completo (nombres y apellidos, solo letras)."
                    else:
                        state['full_name'] = message_text.title()
                        state['step'] = 'id_type'
                        # Replace the old message with the list menu
                        await WhatsAppService.send_list_menu(
                            to=to,
                            body="Por favor selecciona tu tipo de documento:",
                            button_text="Ver opciones",
                            sections= ID_TYPE_SECTIONS
                        )
                        return  # Return early as we've sent the menu

                case 'id_type':
                    # Handle the list_reply response
                    if isinstance(message, dict) and message.get('type') == 'interactive':
                        list_reply = message.get('interactive', {}).get('list_reply', {})
                        selected_id = list_reply.get('id')
                        if selected_id in ID_TYPES:
                            state['id_type'] = selected_id
                            state['step'] = 'id_number'
                            response = STEP_MESSAGES['id_number']
                        else:
                            response = f"Tipo de documento no válido. Por favor selecciona una opción de la lista."
                    else:
                        response = "Por favor selecciona una opción de la lista proporcionada."

                case 'id_number':
                    if not message_text.strip().isalnum():
                        response = "El número de documento solo puede contener números y letras."
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
                        response = "Formato de fecha incorrecto. Usa DD/MM/AAAA (ejemplo: 25/12/1990)"

                case 'more_about':
                    if len(message_text.strip()) < 20:
                        response = "Por favor cuéntanos un poco más sobre ti (mínimo 20 caracteres)."
                    else:
                        state['more_about'] = message_text.strip()
                        state['step'] = 'data_auth'
                        response = STEP_MESSAGES['data_auth']

                case 'data_auth':
                    if message_text.strip().upper() != 'SI':
                        response = "Debes aceptar la política de privacidad para completar el registro. Responde 'SI' para aceptar."
                    else:
                        state['data_auth'] = True
                        response = await self.complete_registration(to)

                case _:
                    response = "Estado no reconocido. Reiniciando registro."
                    self.appointment_state.pop(to, None)
                    return

        except Exception as e:
            logger.error(f"Error in registration flow: {str(e)}", exc_info=True)
            response = "Ocurrió un error. Por favor, intenta de nuevo."
            self.appointment_state.pop(to, None)
            return

        # Update state and send response
        self.appointment_state[to] = state
        await WhatsAppService.send_message(to, response)

    async def complete_registration(self, to: str):
        user_data = self.appointment_state[to]
        self.appointment_state.pop(to, None)
        self.remove_handler(to)

        logger.info(f"Registration complete for user {to}: {user_data}")

        await AirtableService.register_user_airtable(to, user_data)

        message =  dedent(f"""
        ¡Registro completado con éxito! 🎉
        Bienvenido a la comunidad Latte Sessions.

        *Estos son tus datos:*
        - Nombre: {user_data['full_name']}
        - Tipo de documento: {user_data['id_type']}
        - Número de documento: {user_data['id_number']}
        - Fecha de nacimiento: {user_data['birth_date']}
        - Más sobre ti: {user_data['more_about']}
        
        Pronto recibirás información sobre nuestros próximos eventos.
        """).strip()
        
        return message
    
    async def handle_ai_conversation(self, sender_id: str, message: dict):
        message_text = message.get("text", {}).get("body", "")
        user_time = time.time()
        
        if message_text.upper() == "LATTEND":
            self.ai_conversation.pop(sender_id, None)
            self.remove_openai_conversation(sender_id)
            await WhatsAppService.send_message(sender_id, "Espero haberte ayudado. Recuerda que puedes contactarme nuevamente cuando gustes.")
            return
        else:
            response = await OpenAIService.generate_response(message_text, self.ai_conversation[sender_id]["messages"])
            self.ai_conversation[sender_id]["messages"].append({
                "user": {"message": message_text, "timestamp": user_time},
                "latte_ai": {"message": response, "timestamp": time.time()}
            })
            await WhatsAppService.send_message(sender_id, response)
 
