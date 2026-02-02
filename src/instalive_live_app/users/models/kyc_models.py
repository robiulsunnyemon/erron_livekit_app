from beanie import Link, Document
from pydantic import Field
from datetime import datetime, timezone
from typing import Optional
from instalive_live_app.core.base.base import BaseCollection
from instalive_live_app.users.models.user_models import UserModel

class KYCModel(BaseCollection):
    user: Link[UserModel]
    id_front: str  # URL for Front ID image
    id_back: str   # URL for Back ID image
    status: str = Field(default="pending") # pending, approved, rejected
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "kyc_verifications"
