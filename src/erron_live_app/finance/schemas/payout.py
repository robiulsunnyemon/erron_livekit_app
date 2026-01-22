from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime
from uuid import UUID
from erron_live_app.core.base.base import BaseResponse
from erron_live_app.users.schemas.user_schemas import UserResponse
from erron_live_app.finance.models.payout import PayoutStatus

# --- Beneficiary Schemas ---

class BeneficiaryCreate(BaseModel):
    method: str  # "bank_transfer", "paypal", "venmo"
    details: Dict[str, str]

class BeneficiaryResponse(BaseResponse):
    user: Optional[UserResponse] = None
    method: str
    details: Dict[str, str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# --- Payout Config Schemas ---

class PayoutConfigResponse(BaseResponse):
    token_rate_usd: float
    platform_fee_percent: float
    min_withdrawal_amount: float
    updated_at: datetime

    class Config:
        from_attributes = True

class PayoutConfigUpdate(BaseModel):
    token_rate_usd: Optional[float] = None
    platform_fee_percent: Optional[float] = None
    min_withdrawal_amount: Optional[float] = None

# --- Payout Request Schemas ---

class PayoutRequestCreate(BaseModel):
    amount_coins: float
    beneficiary_id: UUID

class PayoutRequestResponse(BaseResponse):
    user: Optional[UserResponse] = None
    # We might embed valid Beneficiary details, or just ID. For dashboard, details are useful.
    beneficiary: Optional[BeneficiaryResponse] = None
    
    amount_coins: float
    amount_fiat: float
    platform_fee: float
    final_amount: float
    status: PayoutStatus
    admin_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PayoutActionRequest(BaseModel):
    action: str # "APPROVE", "DECLINE"
    note: Optional[str] = None

class PayoutRequestUpdate(BaseModel):
    admin_note: Optional[str] = None
    status: Optional[str] = None

