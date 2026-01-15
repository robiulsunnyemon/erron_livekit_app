from beanie import Link, before_event, Save, Replace
from pydantic import Field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from erron_live_app.core.base.base import BaseCollection
from erron_live_app.users.models.user_models import UserModel

class TransactionType(str, Enum):
    CREDIT = "credit"  # যোগ হবে (e.g. Received Gift, Topup)
    DEBIT = "debit"    # বিয়োগ হবে (e.g. Sent Gift, Entry Fee)

class TransactionReason(str, Enum):
    GIFT_SENT = "gift_sent"
    GIFT_RECEIVED = "gift_received"
    ENTRY_FEE_PAID = "entry_fee_paid"
    ENTRY_FEE_RECEIVED = "entry_fee_received"
    TOPUP = "topup"
    WITHDRAW = "withdraw"
    HOST_STREAM_FEE_PAID = "host_stream_fee_paid"

class TransactionModel(BaseCollection):
    user: Link[UserModel]
    amount: float
    transaction_type: TransactionType
    reason: TransactionReason
    related_entity_id: Optional[str] = None # e.g. LiveStream ID, GiftLog ID
    description: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "transactions"
