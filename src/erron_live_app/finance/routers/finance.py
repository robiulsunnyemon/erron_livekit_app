from fastapi import APIRouter, Depends
from typing import List
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.finance.models.transaction import TransactionModel
from erron_live_app.finance.schemas.finance import TransactionResponse
from erron_live_app.users.utils.populate_kyc import populate_user_kyc

router = APIRouter(prefix="/finance", tags=["Finance"])

@router.get("/history", response_model=List[TransactionResponse])
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
    
    # Populate KYC for each user
    transactions_with_kyc = []
    for transaction in transactions:
        trans_dict = transaction.model_dump()
        if transaction.user:
            user_with_kyc = await populate_user_kyc(transaction.user)
            trans_dict["user"] = user_with_kyc
        transactions_with_kyc.append(trans_dict)
    
    return transactions_with_kyc
