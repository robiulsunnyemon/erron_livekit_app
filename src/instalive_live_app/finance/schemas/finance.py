from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from instalive_live_app.core.base.base import BaseResponse
from instalive_live_app.users.schemas.user_schemas import UserResponse
from instalive_live_app.finance.models.transaction import TransactionType, TransactionReason


class TransactionResponse(BaseResponse):
    user: UserResponse
    amount: int
    transaction_type: TransactionType
    reason: TransactionReason
    related_entity_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class StripePaymentRequest(BaseModel):
    amount: float # in USD (e.g. 0.99)
    tokens: int   # number of tokens to add

class StripePaymentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
