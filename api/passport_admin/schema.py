from ninja import Schema
from typing import List, Optional


class GenericResponse(Schema):
    status: str


class Banner(Schema):
    content: str
    link: Optional[str] = None
    banner_id: int
    application: str = "passport"


class NotificationSchema(Schema):
    notification_id: str
    type: str
    content: str
    link: Optional[str] = None
    link_text: Optional[str] = None
    is_read: bool


class NotificationResponse(Schema):
    items: List[NotificationSchema]


class ChainSchema(Schema):
    id: str
    name: str


class NotificationPayload(Schema):
    expired_chain_ids: Optional[List[ChainSchema]] = None


class DismissPayload(Schema):
    dismissal_type: str
