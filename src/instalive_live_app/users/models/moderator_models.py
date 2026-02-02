from beanie import before_event, Replace, Save, Link
from pydantic import EmailStr, Field
from typing import Optional, List
from datetime import datetime, timezone
from instalive_live_app.core.base.base import BaseCollection
from instalive_live_app.users.utils.user_role import UserRole
from instalive_live_app.users.models.user_models import UserModel

class ModeratorModel(BaseCollection):
    full_name: str
    username: str = Field(unique=True)
    email: EmailStr = Field(unique=True)
    password: str
    role: UserRole = Field(default=UserRole.MODERATOR)
    
    # Permissions as boolean fields
    can_view_reports: bool = Field(default=False)
    can_review_appeals: bool = Field(default=False)
    can_access_live_monitor: bool = Field(default=False)
    can_system_config: bool = Field(default=False)
    can_issue_bans: bool = Field(default=False)
    can_manage_users: bool = Field(default=False)
    can_approve_payouts: bool = Field(default=False)

    # Performance Counters
    suspended_count: int = Field(default=0)
    activated_count: int = Field(default=0)
    inactivated_count: int = Field(default=0)
    reported_count: int = Field(default=0)
    appeal_count: int = Field(default=0)

    created_by: Link[UserModel]
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @before_event([Save, Replace])
    def update_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)

    class Settings:
        name = "moderators"
