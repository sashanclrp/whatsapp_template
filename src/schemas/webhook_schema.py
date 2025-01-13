from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class TextMessage(BaseModel):
    body: str


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


class Message(BaseModel):
    from_: str = Field(..., alias='from')
    id: str
    timestamp: str
    type: str
    text: Optional[Dict[str, Any]] = None
    interactive: Optional[Interactive] = None

    class Config:
        allow_population_by_field_name = True


class Status(BaseModel):
    id: str
    status: str
    timestamp: str
    recipient_id: str
    conversation: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None


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
