from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from erron_live_app.core.base.base import BaseResponse
from erron_live_app.users.schemas.user_schemas import UserResponse
from erron_live_app.finance.models.transaction import TransactionType, TransactionReason


class TransactionResponse(BaseResponse):
    user: UserResponse
    amount: float
    transaction_type: TransactionType
    reason: TransactionReason
    related_entity_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
