from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from instalive_live_app.core.base.base import BaseResponse
from instalive_live_app.notifications.models import NotificationType

class NotificationResponse(BaseResponse):
    type: NotificationType
    title: str
    body: str
    related_entity_id: Optional[str] = None
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class NotificationMarkRead(BaseModel):
    is_read: bool = True


