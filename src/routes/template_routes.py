from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, conlist, Field, RootModel, model_validator, field_validator
from typing import Any, Dict, List, Optional
import asyncio

from services.message_handler.template_handler.template_sender import send_media_template
from utils.logger import logger

router = APIRouter()

# Define the custom exception handler function.
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    custom_errors = []
    for error in exc.errors():
        loc = error.get("loc", [])
        field = loc[-1] if loc else "field"
        msg = error.get("msg", "")
        if error.get("type") == "missing":
            msg = f"The field '{field}' is required and was not provided. Please add '{field}' to your payload."
        # You can add additional customization based on error type or field here.
        custom_errors.append({
            "loc": loc,
            "msg": msg,
            "type": error.get("type")
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": custom_errors},
    )

class TemplateRequestItem(BaseModel):
    template_name: str
    language_code: str
    user_waid: str
    media_type: str  # Required field.
    media_id: Optional[str] = None  # Optional.
    media_url: Optional[str] = None  # Optional.
    parameters: Optional[List[Dict]] = None  # Must be a list of dictionaries if provided.
    redis_user_data: Dict[str, Any]

    @field_validator('parameters', mode='before')
    def validate_parameters(cls, value):
        if value is None:
            return value
        if not isinstance(value, list):
            raise ValueError("parameters must be a list of dictionaries.")
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("Each element in parameters must be a dictionary.")
        return value

    @model_validator(mode="after")
    def check_media_fields(self) -> "TemplateRequestItem":
        if self.media_id and self.media_url:
            raise ValueError("Provide only one of 'media_id' or 'media_url', not both.")
        if not self.media_id and not self.media_url:
            raise ValueError("Either 'media_id' or 'media_url' must be provided.")
        return self

TemplateRequestList = conlist(TemplateRequestItem, min_length=1, max_length=100)

class SendTemplatesRequest(RootModel):
    root: List[TemplateRequestItem] = Field(..., min_length=1, max_length=100)
    
    def __iter__(self):
        return iter(self.root)
        
    def __getitem__(self, item):
        return self.root[item]

@router.post("/send-media-template")
async def send_template(templates: SendTemplatesRequest):
    """
    Endpoint to send one or more template messages concurrently and return a summary by template name.
    
    Expects a JSON body containing a non-empty list of template requests:
    [
        {
            "template_name": "welcome",
            "language_code": "en",
            "user_waid": "123456789",
            "media_type": "image", # Required field
            "media_id": "media123", # Can be a media id or a media url
            "media_url": "https://example.com/media.jpg",
            "parameters": [{"type": "text", "parameter_name": "name", "text": "María"}],
            "redis_user_data": { ... }
        },
        ...
    ]
    """
    tasks = []
    for item in templates.root:
        try:
            tasks.append(
                asyncio.create_task(
                    send_media_template(
                        template_name=item.template_name,
                        language_code=item.language_code,
                        user_waid=item.user_waid,
                        media_type=item.media_type,
                        media_id=item.media_id,
                        media_url=item.media_url,
                        parameters=item.parameters,
                        redis_user_data=item.redis_user_data,
                    )
                )
            )
        except Exception as e:
            logger.error(f"Error creating task for {item.template_name}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    error_details = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Task failed: {str(result)}", exc_info=True)
            error_details.append(str(result))
    
    if error_details:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Partial failure processing templates",
                "errors": error_details,
                "success_count": len(results) - len(error_details)
            }
        )
    
    # Collect successful results (non-exception objects)
    successful_results = [r for r in results if not isinstance(r, Exception)]
    
    # Create summary from actual execution results
    summary = {}
    for result in successful_results:
        template_name = result["template_name"]
        summary[template_name] = summary.get(template_name, 0) + 1
    
    # Return both summary and individual results if needed
    return {
        "status": 200,
        "summary": summary,
        "total_sent": len(successful_results),
        "details": successful_results  # Optional: include individual results
    }