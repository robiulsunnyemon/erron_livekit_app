from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from erron_live_app.core.base.base import BaseResponse
from erron_live_app.users.schemas.user_schemas import UserResponse, ModeratorResponse


class LiveStartRequest(BaseModel):
    is_premium: bool = False
    entry_fee: int = 0


class LiveJoinRequest(BaseModel):
    channel_name: str


class LiveStreamResponse(BaseResponse):
    host: UserResponse
    channel_name: str
    title: str
    category: str
    thumbnail: str
    is_premium: bool
    entry_fee: float
    start_time: datetime
    end_time: Optional[datetime] = None
    total_likes: int
    earn_coins: int
    livekit_token:str
    total_views: int
    total_comments: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ActiveStreamsStatsResponse(BaseModel):
    total: int
    free: int
    paid: int


class PendingReportsStatsResponse(BaseModel):
    total: int
    high_priority: int


class LiveStreamReportResponse(BaseResponse):
    session: LiveStreamResponse
    reporter_user: Optional[UserResponse] = None
    reporter_moderator: Optional["ModeratorResponse"] = None
    category: str
    description: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True