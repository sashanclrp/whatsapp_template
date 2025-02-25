from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

###################
# BASE MODELS
###################
class BaseMediaMessage(BaseModel):
    id: str
    mime_type: str
    sha256: str


###################
# INTERACTIVE COMPONENTS
###################
class ButtonReply(BaseModel):
    id: str
    title: str


class ListReply(BaseModel):
    id: str
    title: str
    description: str


class Interactive(BaseModel):
    type: str
    button_reply: Optional[ButtonReply] = None
    list_reply: Optional[ListReply] = None


class Button(BaseModel):
    payload: str
    text: str


###################
# MESSAGE CONTENT TYPES
###################
class ImageMessage(BaseMediaMessage):
    caption: Optional[str] = None


class VideoMessage(BaseMediaMessage):
    caption: Optional[str] = None


class AudioMessage(BaseMediaMessage):
    voice: Optional[bool] = None  # For voice messages


class DocumentMessage(BaseMediaMessage):
    filename: str
    caption: Optional[str] = None


class StickerMessage(BaseMediaMessage):
    animated: Optional[bool] = None  # Indicates if the sticker is animated


###################
# MESSAGE CONTAINERS
###################
class Message(BaseModel):
    from_: str = Field(..., alias='from')
    id: str
    timestamp: str
    type: str
    context: Optional[Dict[str, Any]] = None
    text: Optional[Dict[str, Any]] = None
    interactive: Optional[Interactive] = None
    button: Optional[Button] = None
    image: Optional[ImageMessage] = None
    video: Optional[VideoMessage] = None
    audio: Optional[AudioMessage] = None
    document: Optional[DocumentMessage] = None
    sticker: Optional[StickerMessage] = None

    class Config:
        populate_by_name = True


###################
# STATUS MODELS
###################
class Status(BaseModel):
    id: str
    status: str
    timestamp: str
    recipient_id: str
    conversation: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None


###################
# WEBHOOK STRUCTURE
###################
class Value(BaseModel):
    messaging_product: str
    metadata: Dict[str, Any]
    contacts: Optional[List[Dict[str, Any]]] = None
    messages: Optional[List[Message]] = None
    statuses: Optional[List[Status]] = None


class Change(BaseModel):
    value: Value
    field: str


class Entry(BaseModel):
    id: str
    changes: List[Change]


class WebhookMessage(BaseModel):
    object: str
    entry: List[Entry]
