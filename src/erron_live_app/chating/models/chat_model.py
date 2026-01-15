from beanie import Link
from pydantic import Field
from datetime import datetime, timezone
from typing import Optional
from erron_live_app.core.base.base import BaseCollection
from erron_live_app.users.models.user_models import UserModel

class ChatMessageModel(BaseCollection):
    sender: Link[UserModel]
    receiver: Link[UserModel]
    message: Optional[str] = None
    image_url: Optional[str] = None
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "chat_messages"
