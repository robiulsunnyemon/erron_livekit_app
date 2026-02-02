from beanie import Link, before_event, Save, Replace
from pydantic import Field
from datetime import datetime, timezone
from typing import Optional
from instalive_live_app.core.base.base import BaseCollection
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.streaming.models.streaming import LiveStreamModel



class GiftLogModel(BaseCollection):
    sender: Link[UserModel]
    receiver: Link[UserModel]
    session: Link[LiveStreamModel]

    price_at_time: int # Price paid (in case gift price changes later)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "gift_logs"
