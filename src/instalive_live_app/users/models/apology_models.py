from datetime import datetime, timezone
from typing import Optional
from beanie import Link, before_event, Replace, Save
from pydantic import Field
from instalive_live_app.core.base.base import BaseCollection
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.utils.apology_status import ApologyStatus

class ApologyModel(BaseCollection):
    user: Link[UserModel]
    message: str
    status: ApologyStatus = Field(default=ApologyStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @before_event([Save, Replace])
    def update_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)

    class Settings:
        name = "apologies"
