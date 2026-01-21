from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, cast
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.streaming.models.streaming import LiveStreamModel
from erron_live_app.streaming.models.gifts import GiftLogModel
from erron_live_app.finance.models.transaction import TransactionModel, TransactionType, TransactionReason

router = APIRouter(prefix="/streaming/gifts", tags=["Gifting"])



from erron_live_app.admin.utils import check_feature_access

@router.post("/send")
async def send_coins(
    amount: float,
    session_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    await check_feature_access("gifting")
    # 1. Validate Input
    if amount <= 0:
         raise HTTPException(status_code=400, detail="Amount must be positive")

    stream = await LiveStreamModel.get(session_id, fetch_links=True)
    if not stream or stream.status != "live":
        raise HTTPException(status_code=404, detail="Live stream ended or not found")
    
    host_user = cast(UserModel, stream.host)
    if host_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send coins to yourself")

    # 2. Check Balance
    if current_user.coins < amount:
        raise HTTPException(status_code=402, detail="Insufficient coins")

    # 3. Execute Transaction
    
    # Deduct from Sender
    current_user.coins -= amount
    await current_user.save()
    
    # Add to Host
    host_user.coins += amount
    await host_user.save()
    
    # Update Stream Stats
    stream.earn_coins += int(amount)
    await stream.save()

    # 4. Log Gift (Coin Transfer)
    gift_log = GiftLogModel(
        sender=current_user.to_ref(),
        receiver=host_user.to_ref(),
        session=stream.to_ref(),

        price_at_time=amount
    )
    await gift_log.insert()

    # 5. Log Transactions
    # Debit for Sender
    await TransactionModel(
        user=current_user.to_ref(),
        amount=amount,
        transaction_type=TransactionType.DEBIT,
        reason=TransactionReason.GIFT_SENT,
        related_entity_id=str(gift_log.id),
        description=f"Sent {amount} coins to {host_user.first_name}"
    ).insert()

    # Credit for Host
    await TransactionModel(
        user=host_user.to_ref(),
        amount=amount,
        transaction_type=TransactionType.CREDIT,
        reason=TransactionReason.GIFT_RECEIVED,
        related_entity_id=str(gift_log.id),
        description=f"Received {amount} coins from {current_user.first_name}"
    ).insert()

    return {"status": "success", "new_balance": current_user.coins, "sent_amount": amount}
