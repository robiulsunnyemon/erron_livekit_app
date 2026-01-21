from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, HTTPException, status
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.models.moderator_models import ModeratorModel
from erron_live_app.users.utils.user_role import UserRole
from erron_live_app.admin.models import SystemConfigModel, SecurityAuditLogModel
from erron_live_app.admin.schemas import SystemConfigResponse, SystemConfigUpdate, SecurityAuditLogResponse
from erron_live_app.admin.utils import get_system_config, log_admin_action

router = APIRouter(prefix="/admin", tags=["Admin System"])







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
