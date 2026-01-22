from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from beanie import Document, Link
from pydantic import Field
from erron_live_app.core.base.base import BaseCollection
from erron_live_app.users.models.user_models import UserModel

class NotificationType(str, Enum):
    ACCOUNT = "ACCOUNT"
    LIVE = "LIVE"
    FINANCE = "FINANCE"
    SYSTEM = "SYSTEM"

class NotificationModel(BaseCollection):
    user: Link[UserModel]
    type: NotificationType
    title: str
    body: str
    related_entity_id: Optional[str] = None
    is_read: bool = False
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "notifications"
