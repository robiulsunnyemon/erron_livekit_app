from beanie import Document
from pydantic import Field
from datetime import datetime, timezone
from instalive_live_app.core.base.base import BaseCollection

class ProcessedStripeEvent(BaseCollection):
    event_id: str = Field(unique=True)
    type: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "processed_stripe_events"
