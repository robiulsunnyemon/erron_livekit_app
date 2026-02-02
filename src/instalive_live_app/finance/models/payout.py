from typing import Optional, Dict
from datetime import datetime, timezone
from beanie import Document, Link
from pydantic import Field
from enum import Enum
from instalive_live_app.core.base.base import BaseCollection
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.models.moderator_models import ModeratorModel

class PayoutConfigModel(BaseCollection):
    """
    Singleton configuration for payout settings.
    """
    token_rate_usd: float = 0.01  # 1 Coin = $0.01 USD
    platform_fee_percent: float = 30.0  # 30% platform fee
    min_withdrawal_amount: float = 50.0 # Minimum $50 USD to withdraw
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "payout_config"

    @classmethod
    async def get_config(cls) -> "PayoutConfigModel":
        config = await cls.find_one()
        if not config:
            config = cls()
            await config.insert()
        return config


class BeneficiaryModel(BaseCollection):
    """
    User's saved payment methods (Bank, PayPal, etc.)
    """
    user: Link[UserModel]
    method: str  # "bank_transfer", "paypal", "venmo"
    details: Dict[str, str] # e.g. {"account_holder_name": "...", "account_number": "..."}
    is_active: bool = True
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "beneficiaries"


class PayoutStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class PayoutRequestModel(BaseCollection):
    """
    Withdrawal requests.
    """
    user: Link[UserModel]
    beneficiary: Link[BeneficiaryModel]
    
    amount_coins: float
    amount_fiat: float  # Value in USD
    platform_fee: float  # Fee deducted in USD
    final_amount: float  # Final amount to be sent in USD
    
    status: PayoutStatus = PayoutStatus.PENDING
    
    admin_note: Optional[str] = None
    reviewed_by_admin: Optional[Link[UserModel]] = None
    reviewed_by_moderator: Optional[Link[ModeratorModel]] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "payout_requests"
