import time
from typing import Any, Dict, List, Optional
from utils.logger import logger
from services.whatsapp_services.send_templates import WhatsAppServiceTemplates
from utils.redis.redis_handler import RedisHandler

async def send_media_template(
    template_name: str,
    language_code: str,
    user_waid: str,
    media_type: str,
    media_id: str,
    media_url: str,
    parameters: Optional[List[Dict]] = None,
    redis_user_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Asynchronously send a media template message using WhatsAppServiceTemplates.media_template.
    
    Additionally, updates Redis by:
      - Creating a user record with an added field "template_status" set to "locked".
      - Creating a handler state with handler name "tmp_{template_name}" and state:
            {"step": "{template_name}_sent", "sent": <current_epoch_time>}
    
    Args:
        template_name (str): Name of the template.
        language_code (str): Language code (e.g., "en", "es").
        user_waid (str): The WhatsApp ID/phone number of the recipient.
        media_type (str): The type of media to send (e.g., "image", "video", "document").
        media_id (str): The media identifier for the template.
        media_url (str): URL of the media to be sent.
        parameters (Optional[List[Dict]]): Optional body parameters for the template.
        redis_user_data (Dict[str, Any]): Additional user data for Redis.
    
    Returns:
        Dict[str, Any]: The response from the WhatsApp API as returned by WhatsAppServiceTemplates.media_template.
    """
    logger.info(
        f"Sending media template '{template_name}' in '{language_code}' to {user_waid} with "
        f"parameters: {parameters} and media_id: {media_id}"
    )
    
    # Convert body parameter(s) to list if provided as a dict
    body_parameters = None
    if parameters:
        if isinstance(parameters, list):
            body_parameters = parameters
        else:
            raise ValueError("Parameters must be a list of dictionaries")

    # Call WhatsAppServiceTemplates.media_template
    response = await WhatsAppServiceTemplates.media_template(
        phone_number=user_waid,
        template_name=template_name,
        media_type=media_type,
        media_id=media_id,
        media_url=media_url,
        body_parameters=body_parameters,
        language_code=language_code
    )

    # Update Redis: create or update the user record with template_status locked
    if redis_user_data is None:
        redis_user_data = {}
    redis_user_data["template_status"] = "locked"
    redis_user_data["template_name"] = template_name
    await RedisHandler.create_user_record(user_waid, redis_user_data)

    # Create a handler state in Redis for this template operation
    handler_name = f"tmp_{template_name}"
    state_data = {
        "step": f"{template_name}_sent",
        "sent": time.time()
    }
    await RedisHandler.set_handler_state(handler_name, user_waid, state_data)
    
    # Attach the template name to the response so the route can use it in the summary.
    if isinstance(response, dict):
        response["template_name"] = template_name
    else:
        response = {"template_name": template_name, "response": response}
    
    return response