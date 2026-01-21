from typing import Union, Optional
from fastapi import HTTPException, status
from erron_live_app.admin.models import SystemConfigModel, SecurityAuditLogModel
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.models.moderator_models import ModeratorModel

async def get_system_config() -> SystemConfigModel:
    """
    Wrapper to get the system configuration.
    """
    return await SystemConfigModel.get_config()

async def check_feature_access(feature_name: str):
    """
    Checks if a specific feature is enabled.
    Raises HTTPException if disabled.
    """
    config = await get_system_config()
    
    is_enabled = True
    if feature_name == "registration":
        is_enabled = config.enable_registration
    elif feature_name == "paid_streams":
        is_enabled = config.enable_paid_streams
    elif feature_name == "gifting":
        is_enabled = config.enable_gifting
        
    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"{feature_name.replace('_', ' ').title()} is currently disabled by the administrator"
        )

async def log_admin_action(
    actor: Union[UserModel, ModeratorModel],
    action: str,
    target: str,
    severity: str = "Low",
    details: Optional[str] = None
):
    """
    Logs an administrative action to the database.
    Key helper for tracking emergency switch toggles and other sensitive actions.
    """
    log_entry = SecurityAuditLogModel(
        action=action,
        target=target,
        severity=severity,
        details=details
    )
    
    if isinstance(actor, UserModel):
        log_entry.actor_user = actor.to_ref()
    elif isinstance(actor, ModeratorModel):
        log_entry.actor_moderator = actor.to_ref()
        
    await log_entry.insert()
