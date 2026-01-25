from beanie import before_event, Replace, Save
from pydantic import EmailStr, Field
from typing import Optional
from datetime import datetime, timezone
from erron_live_app.core.base.base import BaseCollection
from erron_live_app.users.utils.account_status import AccountStatus
from erron_live_app.users.utils.user_role import UserRole
from typing import List
from beanie import Link

class UserModel(BaseCollection):

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    coins:float=50.0
    phone_number: Optional[str] =None
    password: Optional[str] = None
    is_verified: bool = False
    country:Optional[str]=None
    gender:Optional[str]=None
    date_of_birth:Optional[str]=None
    bio:Optional[str]=None

    is_online: bool = Field(default=False)
    following: List[Link["UserModel"]] = [] 
    following_count: int = Field(default=0)
    followers_count: int = Field(default=0)
    total_likes: int = Field(default=0)
    shady:float = Field(default=0.0)

    account_status: AccountStatus = Field(default=AccountStatus.ACTIVE)
    otp: Optional[str] = None
    role: Optional[UserRole] = Field(default=UserRole.USER)
    profile_image: Optional[str] = Field(default=None)
    cover_image: Optional[str] = Field(default=None)
    auth_provider: str =  Field(default="email")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Auto-update "updated_at" on update
    @before_event([Save, Replace])
    def update_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)

    class Settings:
        name = "users"

