from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from erron_live_app.core.base.base import BaseResponse
from erron_live_app.users.schemas.user_schemas import UserResponse
from beanie import PydanticObjectId


class ReactionSchema(BaseModel):
    user_id: str
    emoji: str


class ChatMessageResponse(BaseResponse):
    sender: UserResponse
    receiver: UserResponse
    message: Optional[str] = None
    image_url: Optional[str] = None
    is_read: bool
    replied_to_id: Optional[PydanticObjectId] = None
    reactions: List[ReactionSchema] = []
    created_at: datetime

    class Config:
        from_attributes = True


class OtherUserInfo(BaseModel):
    id: str
    first_name: Optional[str]
    last_name: Optional[str]
    profile_image: Optional[str]
    is_online: bool


class ConversationResponse(BaseModel):
    other_user: OtherUserInfo
    last_message: Optional[str]
    last_image_url: Optional[str]
    created_at: datetime
    unread_count: int

    class Config:
        from_attributes = True
