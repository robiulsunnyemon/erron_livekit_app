from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, HTTPException, status
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.models.moderator_models import ModeratorModel
from erron_live_app.users.utils.user_role import UserRole
from erron_live_app.admin.models import SystemConfigModel, SecurityAuditLogModel
from erron_live_app.admin.schemas import (
    SystemConfigResponse, SystemConfigUpdate, SecurityAuditLogResponse,
    UserStatsResponse, MonthlyUserStat,
    RevenueTrendResponse, MonthlyRevenueStat, FinanceStatsResponse
)
from erron_live_app.admin.utils import get_system_config, log_admin_action
from datetime import datetime
from erron_live_app.finance.models.transaction import TransactionModel, TransactionReason
from erron_live_app.finance.models.payout import PayoutRequestModel, PayoutStatus, PayoutConfigModel
import calendar



router = APIRouter(prefix="/admin", tags=["Admin System"])



@router.get("/stats/users/monthly", response_model=UserStatsResponse)
async def get_monthly_user_stats(
    year: int,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
):
    """
    Get the count of new user registrations for each month of the specified year.
    """
    start_date = datetime(year, 1, 1)
    if year == 9999: # Boundary check or handling future? Just simple logic for now.
         end_date = datetime(year, 12, 31, 23, 59, 59)
    else:
         end_date = datetime(year, 12, 31, 23, 59, 59)

    # Aggregation Pipeline
    pipeline = [
        {
            "$match": {
                "created_at": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
        },
        {
            "$group": {
                "_id": {"$month": "$created_at"},
                "count": {"$sum": 1}
            }
        }
    ]

    results = await UserModel.get_motor_collection().aggregate(pipeline).to_list(length=12)
    
    # Process results into a dictionary for easy lookup
    month_counts = {item["_id"]: item["count"] for item in results}
    
    # Build complete list for all 12 months
    monthly_stats = []
    total_users = 0
    for i in range(1, 13):
        count = month_counts.get(i, 0)
        total_users += count
        monthly_stats.append(MonthlyUserStat(
            month=calendar.month_abbr[i], # Jan, Feb...
            count=count
        ))
        
    return UserStatsResponse(
        year=year,
        total_new_users=total_users,
        monthly_counts=monthly_stats
    )


async def get_admin_or_moderator(
    current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
) -> Union[UserModel, ModeratorModel]:
    """
    Dependency to ensure the user is an admin or a moderator with appropriate permissions.
    """
    if isinstance(current_user, UserModel):
        if current_user.role != UserRole.ADMIN:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return current_user
    
    if isinstance(current_user, ModeratorModel):
        # Moderators can access if they have 'can_system_config' permission
        if not current_user.can_system_config:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage system config")
        return current_user

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@router.get("/config", response_model=SystemConfigResponse)
async def get_config(
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """
    Get current system configuration (feature flags).
    """
    return await get_system_config()


@router.patch("/config", response_model=SystemConfigResponse)
async def update_config(
    data: SystemConfigUpdate,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """
    Toggle emergency switches. Logs the action.
    """
    config = await get_system_config()
    
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
        
    for key, value in updates.items():
        setattr(config, key, value)
        
    await config.save()
    
    # Audit Log
    actor_name = current_user.email if isinstance(current_user, UserModel) else current_user.username
    details = ", ".join([f"{k}={v}" for k, v in updates.items()])
    
    await log_admin_action(
        actor=current_user,
        action="Updated System Config",
        target="System Settings",
        severity="High",
        details=f"Changed settings: {details}"
    )
    
    return config


@router.get("/audit-logs", response_model=List[SecurityAuditLogResponse])
async def get_audit_logs(
    limit: int = 20,
    skip: int = 0,
    severity: Optional[str] = None,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """
    Retrieve security audit logs.
    """
    # Moderators should have 'can_view_reports' or similar permissions? 
    # For now, reusing the dependency logic which checks 'can_system_config'.
    # If we want detailed permissions, checks should be more granular.
    
    query = SecurityAuditLogModel.find_all(fetch_links=True)
    if severity:
        query = query.find(SecurityAuditLogModel.severity == severity)
        
    logs = await query.sort("-timestamp").skip(skip).limit(limit).to_list()
    
    # Helper to format response
    response_logs = []
    for log in logs:
        actor_name = "Unknown"
        if log.actor_user:
            actor_name = log.actor_user.email
        elif log.actor_moderator:
            actor_name = log.actor_moderator.username
            
        log_dict = log.model_dump()
        log_dict['actor_name'] = actor_name
        response_logs.append(log_dict)
        
    return response_logs


@router.get("/stats/finance/revenue-trend", response_model=RevenueTrendResponse)
async def get_revenue_trend(
    year: int,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """
    Get monthly revenue trend for a specific year.
    Revenue is calculated from 'topup' transactions converted to USD.
    """
    payout_config = await PayoutConfigModel.get_config()
    token_rate = payout_config.token_rate_usd

    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31, 23, 59, 59)

    pipeline = [
        {
            "$match": {
                "reason": TransactionReason.TOPUP,
                "created_at": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
        },
        {
            "$group": {
                "_id": {"$month": "$created_at"},
                "total_coins": {"$sum": "$amount"}
            }
        }
    ]

    results = await TransactionModel.get_motor_collection().aggregate(pipeline).to_list(length=12)
    
    month_map = {item["_id"]: item["total_coins"] for item in results}
    
    monthly_stats = []
    total_revenue = 0.0

    for i in range(1, 13):
        coins = month_map.get(i, 0)
        revenue = coins * token_rate # Convert to USD
        total_revenue += revenue
        
        monthly_stats.append(MonthlyRevenueStat(
            month=calendar.month_abbr[i],
            revenue_usd=revenue
        ))

    return RevenueTrendResponse(
        year=year,
        total_yearly_revenue=total_revenue,
        monthly_revenues=monthly_stats
    )


@router.get("/stats/finance/overview", response_model=FinanceStatsResponse)
async def get_finance_overview(
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    """
    Get lifetime finance statistics (Sales, Payouts, Profit, Pending).
    """
    payout_config = await PayoutConfigModel.get_config()
    token_rate = payout_config.token_rate_usd

    # 1. Total Token Sales (USD)
    # Aggregate all TOPUP transactions
    sales_pipeline = [
        {"$match": {"reason": TransactionReason.TOPUP}},
        {"$group": {"_id": None, "total_coins": {"$sum": "$amount"}}}
    ]
    sales_result = await TransactionModel.get_motor_collection().aggregate(sales_pipeline).to_list(length=1)
    total_sales_coins = sales_result[0]["total_coins"] if sales_result else 0
    total_sales_usd = total_sales_coins * token_rate

    # 2. Total Payouts (USD) - Approved
    payouts_pipeline = [
        {"$match": {"status": PayoutStatus.APPROVED}},
        {"$group": {"_id": None, "total_payout": {"$sum": "$final_amount"}}} # final_amount is in USD
    ]
    payouts_result = await PayoutRequestModel.get_motor_collection().aggregate(payouts_pipeline).to_list(length=1)
    total_payouts_usd = payouts_result[0]["total_payout"] if payouts_result else 0

    # 3. Pending Payouts (USD)
    pending_pipeline = [
        {"$match": {"status": PayoutStatus.PENDING}},
        {"$group": {"_id": None, "total_pending": {"$sum": "$final_amount"}}}
    ]
    pending_result = await PayoutRequestModel.get_motor_collection().aggregate(pending_pipeline).to_list(length=1)
    total_pending_usd = pending_result[0]["total_pending"] if pending_result else 0

    # 4. Profit Margin (USD)
    # Profit = Revenue - Approved Payouts
    profit_margin_usd = total_sales_usd - total_payouts_usd

    return FinanceStatsResponse(
        total_token_sales_usd=total_sales_usd,
        total_payouts_usd=total_payouts_usd,
        profit_margin_usd=profit_margin_usd,
        pending_payouts_usd=total_pending_usd
    )
