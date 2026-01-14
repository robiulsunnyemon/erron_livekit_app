from beanie import before_event, Replace, Save, Link
from pydantic import Field
from datetime import datetime, timezone
from typing import Optional
from erron_live_app.core.base.base import BaseCollection
from erron_live_app.users.models.user_models import UserModel

class LiveStreamModel(BaseCollection):
    host: Link[UserModel]
    channel_name:str
    livekit_token: str = Field(unique=True)
    is_premium: bool = False
    entry_fee: float = 0
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    total_likes: int = 0
    earn_coins:int=0
    total_views: int = 0
    total_comments: int = 0
    status: str = "live"

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @before_event([Save, Replace])
    def update_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)

    class Settings:
        name = "livestreams"



class LiveViewerModel(BaseCollection):
    session: Link[LiveStreamModel]
    user: Link[UserModel]
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fee_paid: float = 0

    class Settings:
        name = "live_viewers"


class LiveCommentModel(BaseCollection):
    session: Link[LiveStreamModel]
    user: Link[UserModel]
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "live_comments"



class LiveLikeModel(BaseCollection):
    session: Link[LiveStreamModel]
    user: Link[UserModel]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "live_likes"


class LiveRatingModel(BaseCollection):
    session: Link[LiveStreamModel]
    user: Link[UserModel]
    rating: int = Field(ge=1, le=5) # 1 to 5 stars
    feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "live_ratings"