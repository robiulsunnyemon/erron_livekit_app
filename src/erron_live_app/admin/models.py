from typing import Optional, Any
from datetime import datetime, timezone
from beanie import Document, Link
from pydantic import Field
from erron_live_app.core.base.base import BaseCollection
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.models.moderator_models import ModeratorModel

class SystemConfigModel(BaseCollection):
    """
    Singleton document to store system-wide configurations (emergency switches).
    """
    enable_registration: bool = True
    enable_paid_streams: bool = True
    enable_gifting: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "system_config"

    @classmethod
    async def get_config(cls) -> "SystemConfigModel":
        """
        Get the existing config or create a default one if it doesn't exist.
        """
        config = await cls.find_one()
        if not config:
            config = cls()
            await config.insert()
        return config


class SecurityAuditLogModel(BaseCollection):
    """
    Log of administrative and security-critical actions.
    """
    actor_user: Optional[Link[UserModel]] = None
    actor_moderator: Optional[Link[ModeratorModel]] = None
    
    action: str  # e.g., "Banned User", "Updated Config", "Stopped Stream"
    target: str  # e.g., "user@example.com", "System Settings"
    severity: str = "Low"  # "Low", "Medium", "High"
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "security_audit_logs"
