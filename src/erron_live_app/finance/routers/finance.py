from fastapi import APIRouter, Depends
from typing import List
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.finance.models.transaction import TransactionModel

router = APIRouter(prefix="/finance", tags=["Finance"])

@router.get("/history", response_model=List[TransactionModel])
async def get_transaction_history(
    current_user: UserModel = Depends(get_current_user),
    skip: int = 0,
    limit: int = 20
):
    """
    Get the transaction history for the current user.
    Sorted by latest first.
    """
    transactions = await TransactionModel.find(
        TransactionModel.user.id == current_user.id,
        fetch_links=True
    ).sort(-TransactionModel.created_at).skip(skip).limit(limit).to_list()
    
    return transactions
