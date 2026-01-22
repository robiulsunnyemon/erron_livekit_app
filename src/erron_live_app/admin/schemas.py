from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from erron_live_app.core.base.base import BaseResponse


class SystemConfigUpdate(BaseModel):
    enable_registration: Optional[bool] = None
    enable_paid_streams: Optional[bool] = None
    enable_gifting: Optional[bool] = None

class SystemConfigResponse(BaseResponse):
    enable_registration: bool
    enable_paid_streams: bool
    enable_gifting: bool
    updated_at: datetime
    
    # model_config = ConfigDict(from_attributes=True)

class SecurityAuditLogResponse(BaseResponse):
    action: str
    target: str
    severity: str
    details: Optional[str]
    timestamp: datetime
    actor_name: Optional[str] = None # Computed field for display
    
    
    # model_config = ConfigDict(from_attributes=True)

class MonthlyUserStat(BaseModel):
    month: str
    count: int

class UserStatsResponse(BaseModel):
    year: int
    total_new_users: int
    monthly_counts: List[MonthlyUserStat]


class MonthlyRevenueStat(BaseModel):
    month: str
    revenue_usd: float

class RevenueTrendResponse(BaseModel):
    year: int
    total_yearly_revenue: float
    monthly_revenues: List[MonthlyRevenueStat]

class FinanceStatsResponse(BaseModel):
    total_token_sales_usd: float
    total_payouts_usd: float
    profit_margin_usd: float
    pending_payouts_usd: float
