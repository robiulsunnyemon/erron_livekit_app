from pydantic import BaseModel, EmailStr,Field
from typing import Optional,List
from datetime import datetime
from erron_live_app.core.base.base import BaseResponse
from erron_live_app.users.utils.account_status import AccountStatus
from erron_live_app.users.utils.user_role import UserRole
from uuid import UUID

class UserCreate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: EmailStr
    password: Optional[str] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None

class UserResponse(BaseResponse):
    first_name: Optional[str]
    last_name: Optional[str]
    email: EmailStr
    phone_number: Optional[str]
    coins: float
    is_online: bool
    following_count: int = 0
    followers_count: int = 0
    total_likes: int = 0
    is_verified: bool
    profile_image: Optional[str]
    cover_image: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[str] = None
    shady: Optional[float]
    auth_provider: str
    created_at: datetime
    updated_at: datetime
    role: Optional[UserRole] = UserRole.USER
    otp: Optional[str]
    account_status: AccountStatus

    class Config:
        from_attributes = True


class LiveStreamSimpleResponse(BaseResponse):
    title: str = ""
    category: str = ""
    thumbnail: str = ""
    created_at: datetime
    total_views: int = 0
    total_likes: int = 0
    status: str

    class Config:
        from_attributes = True


class ProfileResponse(UserResponse):
    past_streams: List[LiveStreamSimpleResponse] = []


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str



class ResendOTPRequest(BaseModel):
    email: EmailStr



class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str

class ProfileUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    cover_image: Optional[str] = None
    country: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone_number: Optional[str] = None

class ModeratorCreate(BaseModel):
    full_name: str
    email: EmailStr
    username: str
    password: str
    can_view_reports: bool = False
    can_review_appeals: bool = False
    can_access_live_monitor: bool = False
    can_system_config: bool = False
    can_issue_bans: bool = False
    can_manage_users: bool = False
    can_approve_payouts: bool = False

class ModeratorUpdate(BaseModel):
    is_active: Optional[bool] = None
    can_view_reports: Optional[bool] = None
    can_review_appeals: Optional[bool] = None
    can_access_live_monitor: Optional[bool] = None
    can_system_config: Optional[bool] = None
    can_issue_bans: Optional[bool] = None
    can_manage_users: Optional[bool] = None
    can_approve_payouts: Optional[bool] = None

class ModeratorManageUserStatus(BaseModel):
    status: AccountStatus

class ModeratorResponse(BaseResponse):
    full_name: str
    email: EmailStr
    username: str
    role: UserRole
    is_active: bool
    can_view_reports: bool
    can_review_appeals: bool
    can_access_live_monitor: bool
    can_system_config: bool
    can_issue_bans: bool
    can_manage_users: bool
    can_approve_payouts: bool
    
    # Counters
    suspended_count: int
    activated_count: int
    inactivated_count: int
    reported_count: int

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ModeratorProfileResponse(ModeratorResponse):
    pass

class ReportReviewRequest(BaseModel):
    note: Optional[str] = None
    action: str # DISMISS, INACTIVE, SUSPEND

class ReportReviewResponse(BaseResponse):
    report_id: UUID
    moderator_id: UUID
    note: Optional[str]
    action: str
    created_at: datetime

    class Config:
        from_attributes = True