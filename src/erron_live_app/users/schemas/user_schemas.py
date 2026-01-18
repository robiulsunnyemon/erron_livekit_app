from pydantic import BaseModel, EmailStr,Field
from typing import Optional,List
from datetime import datetime
from erron_live_app.core.base.base import BaseResponse
from erron_live_app.users.utils.account_status import AccountStatus
from erron_live_app.users.utils.user_role import UserRole


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
    coins: Optional[float]
    is_online:bool


    following_count: int = Field(default=0)
    followers_count: int = Field(default=0)
    total_likes: int = Field(default=0)

    is_verified: bool
    profile_image: Optional[str]
    shady: Optional[float]
    auth_provider: str
    created_at: datetime
    updated_at: datetime
    role: Optional[UserRole] = Field(default=UserRole.USER)
    otp:Optional[str]
    account_status: AccountStatus

    class Config:
        from_attributes = True


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