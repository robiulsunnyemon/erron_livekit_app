from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from instalive_live_app.core.base.base import BaseResponse
from instalive_live_app.users.utils.apology_status import ApologyStatus
from instalive_live_app.users.schemas.user_schemas import UserResponse, ReportReviewResponse
from instalive_live_app.streaming.schemas.streaming import LiveStreamReportResponse

class ApologyCreate(BaseModel):
    message: str

class ApologyReviewAction(BaseModel):
    action: str # APOLOGY_ACCEPTED, DISMISS

class ApologyResponse(BaseResponse):
    message: str
    status: ApologyStatus
    user: UserResponse
    reports: List[LiveStreamReportResponse] = []
    report_reviews: List[ReportReviewResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
