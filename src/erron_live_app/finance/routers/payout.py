from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Union
from uuid import UUID
from datetime import datetime, timezone
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.models.moderator_models import ModeratorModel
from erron_live_app.users.utils.user_role import UserRole
from erron_live_app.finance.models.payout import PayoutConfigModel, BeneficiaryModel, PayoutRequestModel, PayoutStatus
from erron_live_app.finance.schemas.payout import (
    BeneficiaryCreate, BeneficiaryResponse, 
    PayoutRequestCreate, PayoutRequestResponse, 
    PayoutConfigResponse, PayoutConfigUpdate, 
    PayoutConfigResponse, PayoutConfigUpdate, 
    PayoutActionRequest, PayoutRequestUpdate
)
from erron_live_app.finance.models.transaction import TransactionModel, TransactionType, TransactionReason
from erron_live_app.admin.utils import log_admin_action
from erron_live_app.users.utils.populate_kyc import populate_user_kyc
from erron_live_app.notifications.utils import send_notification
from erron_live_app.notifications.models import NotificationType

router = APIRouter(prefix="/finance", tags=["Finance & Payouts"])

# --- Helper Dependencies ---
async def get_admin_or_moderator(
    current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
):
    if isinstance(current_user, UserModel) and current_user.role == UserRole.ADMIN:
        return current_user
    if isinstance(current_user, ModeratorModel):
        # Check permissions - assume approval needs 'can_approve_payouts'
        if current_user.can_approve_payouts:
             return current_user
    
    raise HTTPException(status_code=403, detail="Permission denied")

# ==========================================
#               USER ENDPOINTS
# ==========================================

@router.post("/beneficiaries", response_model=BeneficiaryResponse, status_code=status.HTTP_201_CREATED)
async def add_beneficiary(
    data: BeneficiaryCreate,
    current_user: UserModel = Depends(get_current_user)
):
    """Link a new bank account or payment method."""
    beneficiary = BeneficiaryModel(
        user=current_user.to_ref(),
        method=data.method,
        details=data.details
    )
    await beneficiary.insert()
    
    # Manually populate user for response to avoid Link validation error
    user_data = await populate_user_kyc(current_user)
    
    response = beneficiary.model_dump()
    response['user'] = user_data
    return response

@router.get("/beneficiaries", response_model=List[BeneficiaryResponse])
async def get_my_beneficiaries(
    current_user: UserModel = Depends(get_current_user)
):
    """List all linked payment methods."""
    beneficiaries = await BeneficiaryModel.find(
        BeneficiaryModel.user.id == current_user.id,
        fetch_links=True
    ).to_list()
    
    # Populate KYC/User properly if needed (UserResponse expects specific fields)
    results = []
    for b in beneficiaries:
        b_dict = b.model_dump()
        if b.user:
            # Re-verify if b.user is fully populated or just a Link depends on fetch_links
            # With fetch_links=True, b.user should be a UserModel
             if isinstance(b.user, UserModel):
                b_dict['user'] = await populate_user_kyc(b.user)
        results.append(b_dict)
        
    return results


@router.post("/payout/request", response_model=PayoutRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_payout(
    data: PayoutRequestCreate,
    current_user: UserModel = Depends(get_current_user)
):
    """Submit a withdrawal request."""
    # 1. Validation
    if data.amount_coins <= 0:
         raise HTTPException(status_code=400, detail="Amount must be positive")
    
    config = await PayoutConfigModel.get_config()
    beneficiary = await BeneficiaryModel.find_one(
        BeneficiaryModel.id == data.beneficiary_id,
        BeneficiaryModel.user.id == current_user.id
    )
    
    if not beneficiary:
        raise HTTPException(status_code=404, detail="Payment method not found")

    if current_user.coins < data.amount_coins:
        raise HTTPException(status_code=400, detail="Insufficient coins balance")

    # 2. Calculation
    fiat_amount = data.amount_coins * config.token_rate_usd
    fee_amount = fiat_amount * (config.platform_fee_percent / 100.0)
    final_amount = fiat_amount - fee_amount
    
    if fiat_amount < config.min_withdrawal_amount:
         raise HTTPException(
             status_code=400, 
             detail=f"Minimum withdrawal amount is ${config.min_withdrawal_amount} (You requested ${fiat_amount:.2f})"
         )

    # 3. Create Request & Deduct Coins
    # We deduct coins immediately to "hold" them. If rejected, we refund.
    current_user.coins -= data.amount_coins
    await current_user.save()
    
    payout_req = PayoutRequestModel(
        user=current_user.to_ref(),
        beneficiary=beneficiary.to_ref(),
        amount_coins=data.amount_coins,
        amount_fiat=fiat_amount,
        platform_fee=fee_amount,
        final_amount=final_amount,
        status=PayoutStatus.PENDING
    )
    await payout_req.insert()
    
    # 4. Log Transaction (Debit)
    await TransactionModel(
        user=current_user.to_ref(),
        amount=data.amount_coins,
        transaction_type=TransactionType.DEBIT,
        reason=TransactionReason.WITHDRAW,
        related_entity_id=str(payout_req.id),
        description=f"Withdrawal request for ${fiat_amount:.2f}"
    ).insert()

    # Notification: Payout Requested
    await send_notification(
        user=current_user,
        title="Payout Requested",
        body=f"Your request for ${fiat_amount:.2f} has been submitted.",
        type=NotificationType.FINANCE,
        related_entity_id=str(payout_req.id)
    )

    # Manual Response Construction
    response = payout_req.model_dump()
    response['user'] = await populate_user_kyc(current_user)
    
    # Populate Beneficiary
    ben_dict = beneficiary.model_dump()
    ben_dict['user'] = response['user'] # BeneficiaryResponse also has user
    response['beneficiary'] = ben_dict
    
    return response


@router.get("/payout/history", response_model=List[PayoutRequestResponse])
async def get_my_payout_history(
    current_user: UserModel = Depends(get_current_user)
):
    """View payout request status."""
    requests = await PayoutRequestModel.find(
        PayoutRequestModel.user.id == current_user.id,
        fetch_links=True
    ).sort("-created_at").to_list()
    
    results = []
    for req in requests:
        req_dict = req.model_dump()
        if req.user and isinstance(req.user, UserModel):
            req_dict['user'] = await populate_user_kyc(req.user)
            
        if req.beneficiary and isinstance(req.beneficiary, BeneficiaryModel):
             ben_dict = req.beneficiary.model_dump()
             # Populate nested user in beneficiary if needed or leave as is if frontend ignores it
             # But Response schema might require it. Let's just set user to same
             ben_dict['user'] = req_dict['user']
             req_dict['beneficiary'] = ben_dict

        results.append(req_dict)
    return results


# ==========================================
#           ADMIN/MODERATOR ENDPOINTS
# ==========================================

@router.get("/admin/config/payout", response_model=PayoutConfigResponse)
async def get_payout_config(
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    return await PayoutConfigModel.get_config()


@router.patch("/admin/config/payout", response_model=PayoutConfigResponse)
async def update_payout_config(
    data: PayoutConfigUpdate,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """Update pricing and fees configuration."""
    config = await PayoutConfigModel.get_config()
    
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
        
    for k, v in updates.items():
        setattr(config, k, v)
    
    config.updated_at = datetime.now(timezone.utc)
    await config.save()
    
    # Audit Log
    actor_identifier = current_user.email if isinstance(current_user, UserModel) else current_user.username
    await log_admin_action(
        actor=current_user,
        action="Updated Payout Config",
        target="Payout Settings",
        severity="High",
        details=f"Updated: {updates}"
    )
    
    return config


@router.get("/admin/payouts", response_model=List[PayoutRequestResponse])
async def get_all_payout_requests(
    status: Union[str, None] = None,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """List pending payments."""
    query = PayoutRequestModel.find_all(fetch_links=True)
    if status:
        query = PayoutRequestModel.find(PayoutRequestModel.status == status, fetch_links=True)
        
    requests = await query.sort("-created_at").to_list()
    
    results = []
    for req in requests:
        req_dict = req.model_dump()
        
        # Populate User
        if req.user and isinstance(req.user, UserModel):
            req_dict['user'] = await populate_user_kyc(req.user)
        
        # Populate Beneficiary
        if req.beneficiary and isinstance(req.beneficiary, BeneficiaryModel):
             ben_dict = req.beneficiary.model_dump()
             # If beneficiary has user link fetched, populate it too?
             # Often unnecessary for admin view to see full user inside beneficiary inside payout req
             # But schema is schema. PayoutRequestResponse -> BeneficiaryResponse -> UserResponse
             if req.beneficiary.user and isinstance(req.beneficiary.user, UserModel):
                 ben_dict['user'] = await populate_user_kyc(req.beneficiary.user)
             
             req_dict['beneficiary'] = ben_dict

        results.append(req_dict)
        
    return results



@router.patch("/admin/payouts/{request_id}", response_model=PayoutRequestResponse)
async def update_payout_request(
    request_id: UUID,
    data: PayoutRequestUpdate,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """
    Update payout request details (Admin Note, Status).
    Warning: Changing status manually here does NOT trigger side effects (refunds/notifications).
    Use /action endpoint for workflow transitions.
    """
    req = await PayoutRequestModel.get(request_id, fetch_links=True)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    for k, v in updates.items():
        setattr(req, k, v)

    req.updated_at = datetime.now(timezone.utc)
    await req.save()

    # Manual Response Construction
    response = req.model_dump()
    if req.user and isinstance(req.user, UserModel):
            response['user'] = await populate_user_kyc(req.user)
            
    if req.beneficiary and isinstance(req.beneficiary, BeneficiaryModel):
             ben_dict = req.beneficiary.model_dump()
             if req.beneficiary.user and isinstance(req.beneficiary.user, UserModel):
                 ben_dict['user'] = await populate_user_kyc(req.beneficiary.user)
             response['beneficiary'] = ben_dict
             
    return response


@router.post("/admin/payouts/{request_id}/action", response_model=PayoutRequestResponse)
async def process_payout_request(
    request_id: UUID,
    data: PayoutActionRequest,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """Approve or Decline a payout request."""
    req = await PayoutRequestModel.get(request_id, fetch_links=True)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    if req.status != PayoutStatus.PENDING:
         raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    # Set Reviewer
    if isinstance(current_user, ModeratorModel):
        req.reviewed_by_moderator = current_user
    else:
        req.reviewed_by_admin = current_user
    
    req.admin_note = data.note

    if data.action.upper() == "APPROVE":
        req.status = PayoutStatus.APPROVED
        # Logic: Payment is handled externally (manually). We just mark it.
        # Coins were already deducted.
        
    elif data.action.upper() == "DECLINE":
        req.status = PayoutStatus.REJECTED
        
        # REFUND COINS
        user = req.user
        if hasattr(user, "fetch"): 
            user = await user.fetch()
            
        if user:
            user.coins += req.amount_coins
            await user.save()
            
            # Log Refund Transaction
            await TransactionModel(
                user=user.to_ref(),
                amount=req.amount_coins,
                transaction_type=TransactionType.CREDIT,
                reason=TransactionReason.TOPUP, # Or make a new reason REFUND
                related_entity_id=str(req.id),
                description=f"Refund for rejected withdrawal: {data.note}"
            ).insert()
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use APPROVE or DECLINE.")

    req.updated_at = datetime.now(timezone.utc)
    await req.save()
    
    # Notification: Payout Action
    target_user = req.user
    if hasattr(target_user, "fetch"):
        target_user = await target_user.fetch()
        
    if target_user:
        status_msg = "approved" if req.status == PayoutStatus.APPROVED else "declined"
        body_msg = f"Your payout request for ${req.amount_fiat:.2f} has been {status_msg}."
        if req.admin_note:
            body_msg += f" Note: {req.admin_note}"
            
        await send_notification(
            user=target_user,
            title=f"Payout {status_msg.capitalize()}",
            body=body_msg,
            type=NotificationType.FINANCE,
            related_entity_id=str(req.id)
        )
    
    # Populate Response
    response = req.model_dump()
    if req.user and isinstance(req.user, UserModel):
            response['user'] = await populate_user_kyc(req.user)
            
    if req.beneficiary and isinstance(req.beneficiary, BeneficiaryModel):
             ben_dict = req.beneficiary.model_dump()
             if req.beneficiary.user and isinstance(req.beneficiary.user, UserModel):
                 ben_dict['user'] = await populate_user_kyc(req.beneficiary.user)
             response['beneficiary'] = ben_dict
             
    return response
