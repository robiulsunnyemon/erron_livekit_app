from uuid import UUID, uuid4
from beanie import Link
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List
from instalive_live_app.core.base.base import BaseCollection
from instalive_live_app.users.models.user_models import UserModel

class Reaction(BaseModel):
    user_id: str
    emoji: str

class ChatMessageModel(BaseCollection):
    sender: Link[UserModel]
    receiver: Link[UserModel]
    message: Optional[str] = None
    image_url: Optional[str] = None
    is_read: bool = False
    replied_to_id: Optional[UUID] = None
    reactions: List[Reaction] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "chat_messages"
