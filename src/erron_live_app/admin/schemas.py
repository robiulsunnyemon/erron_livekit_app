from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID

class SystemConfigUpdate(BaseModel):
    enable_registration: Optional[bool] = None
    enable_paid_streams: Optional[bool] = None
    enable_gifting: Optional[bool] = None

class SystemConfigResponse(BaseModel):
    enable_registration: bool
    enable_paid_streams: bool
    enable_gifting: bool
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SecurityAuditLogResponse(BaseModel):
    id: UUID
    action: str
    target: str
    severity: str
    details: Optional[str]
    timestamp: datetime
    actor_name: Optional[str] = None # Computed field for display
    
    model_config = ConfigDict(from_attributes=True)
