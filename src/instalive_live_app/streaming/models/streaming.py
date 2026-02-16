from beanie import before_event, Replace, Save, Link,after_event, Delete
from pydantic import Field
from datetime import datetime, timezone
from typing import Optional
from instalive_live_app.core.base.base import BaseCollection
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.models.moderator_models import ModeratorModel

class LiveStreamModel(BaseCollection):
    host: Link[UserModel]
    channel_name:str
    title:str=""
    category:str=""
    thumbnail: Optional[str] = Field(default=None)
    livekit_token: str = Field(unique=True)
    is_premium: bool = False
    entry_fee: int = 0
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    total_likes: int = 0
    earn_coins: int = 0
    total_views: int = 0
    total_comments: int = 0
    status: str = "live"

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @before_event([Save, Replace])
    def update_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)

    @after_event(Delete)
    async def cleanup_related_data(self):
        # এই সেশনের সাথে যুক্ত সকল ডাটা ডিলিট করা হচ্ছে
        session_id = self.id

        await LiveViewerModel.find(LiveViewerModel.session.id == session_id).delete()
        await LiveCommentModel.find(LiveCommentModel.session.id == session_id).delete()
        await LiveLikeModel.find(LiveLikeModel.session.id == session_id).delete()
        await LiveRatingModel.find(LiveRatingModel.session.id == session_id).delete()
    class Settings:
        name = "livestreams"



class LiveViewerModel(BaseCollection):
    session: Link[LiveStreamModel]
    user: Link[UserModel]
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fee_paid: int = 0
    has_paid: bool = False

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


class LiveStreamReportModel(BaseCollection):
    session: Link[LiveStreamModel]
    reporter_user: Optional[Link[UserModel]] = None
    reporter_moderator: Optional[Link[ModeratorModel]] = None
    category: str  # e.g., Nudity, Violence, Scam, Harassment
    description: Optional[str] = None
    status: str = "PENDING"  # PENDING, RESOLVED, DISMISSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "live_reports"


class LiveStreamReportReviewModel(BaseCollection):
    report: Link[LiveStreamReportModel]
    moderator: Optional[Link[ModeratorModel]] = None
    admin: Optional[Link[UserModel]] = None
    note: Optional[str] = None
    action: str  # DISMISS, INACTIVE (Warn), SUSPEND (Ban)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "live_report_reviews"


class LiveViewerReportModel(BaseCollection):
    session: Link[LiveStreamModel]
    reporter: Link[UserModel]  # The host who is reporting
    reported_user: Link[UserModel]  # The viewer being reported
    reason: str
    description: Optional[str] = None
    status: str = "PENDING"  # PENDING, RESOLVED, DISMISSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "live_viewer_reports"
