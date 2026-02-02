from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from beanie.operators import In
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.models.moderator_models import ModeratorModel
from instalive_live_app.users.models.apology_models import ApologyModel
from instalive_live_app.streaming.models.streaming import (
    LiveStreamModel, 
    LiveStreamReportModel, 
    LiveStreamReportReviewModel
)
from instalive_live_app.users.utils.account_status import AccountStatus
from instalive_live_app.users.utils.apology_status import ApologyStatus
from instalive_live_app.users.schemas.apology_schemas import ApologyCreate, ApologyReviewAction, ApologyResponse
from instalive_live_app.users.utils.get_current_user import get_current_user
from instalive_live_app.users.utils.user_role import UserRole

router = APIRouter(prefix="/apologies", tags=["Apology System"])

async def get_user_reports_and_reviews(user_id):
    """
    Helper to fetch all reports and reviews for a specific user (host).
    """
    # Find all streams where this user was the host
    streams = await LiveStreamModel.find(LiveStreamModel.host.id == user_id).to_list()
    stream_ids = [s.id for s in streams]
    
    if not stream_ids:
        return [], []
        
    # Find all reports for these streams
    reports = await LiveStreamReportModel.find(
        In(LiveStreamReportModel.session.id, stream_ids),
        fetch_links=True
    ).to_list()
    report_ids = [r.id for r in reports]
    
    if not report_ids:
        return reports, []
        
    # Find all reviews for these reports
    reviews = await LiveStreamReportReviewModel.find(
        In(LiveStreamReportReviewModel.report.id, report_ids),
        fetch_links=True
    ).to_list()
    
    return reports, reviews

@router.post("/", response_model=ApologyResponse)
async def create_apology(
    apology_data: ApologyCreate, 
    current_user: UserModel = Depends(get_current_user)
):
    # Ensure it's a regular user
    if not isinstance(current_user, UserModel):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only regular users can submit apologies")

    apology = ApologyModel(
        user=current_user,
        message=apology_data.message
    )
    await apology.insert()
    
    # Return response without reviews/reports for new post
    db_apology = await ApologyModel.get(apology.id, fetch_links=True)
    return ApologyResponse.model_validate(db_apology)

async def get_admin_or_moderator(
    current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
) -> Union[UserModel, ModeratorModel]:
    if isinstance(current_user, UserModel):
        if current_user.role != UserRole.ADMIN:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        return current_user
    
    if isinstance(current_user, ModeratorModel):
        return current_user

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

@router.get("/", response_model=List[ApologyResponse])
async def get_all_apologies(
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    apologies = await ApologyModel.find(ApologyModel.status=="PENDING",fetch_links=True).sort("-created_at").to_list()
    results = []
    for apology in apologies:
        reports, reviews = await get_user_reports_and_reviews(apology.user.id)
        resp = ApologyResponse.model_validate(apology)
        resp.reports = reports
        resp.report_reviews = reviews
        results.append(resp)
        
    return results

@router.get("/{apology_id}", response_model=ApologyResponse)
async def get_apology_detail(
    apology_id: str,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    apology = await ApologyModel.get(apology_id, fetch_links=True)
    if not apology:
        raise HTTPException(status_code=404, detail="Apology not found")
    
    reports, reviews = await get_user_reports_and_reviews(apology.user.id)
    resp = ApologyResponse.model_validate(apology)
    resp.reports = reports
    resp.report_reviews = reviews
    
    return resp

@router.patch("/{apology_id}/review", response_model=ApologyResponse)
async def review_apology(
    apology_id: str,
    review_data: ApologyReviewAction,
    current_user: Union[UserModel, ModeratorModel] = Depends(get_admin_or_moderator)
):
    apology = await ApologyModel.get(apology_id, fetch_links=True)
    if not apology:
        raise HTTPException(status_code=404, detail="Apology not found")
    
    if review_data.action == "APOLOGY_ACCEPTED":
        apology.status = ApologyStatus.APPROVED
        
        # Access the user and update account status
        user = apology.user
        if isinstance(user, UserModel):
            user.account_status = AccountStatus.ACTIVE
            await user.save()
            
    elif review_data.action == "DISMISS":
        apology.status = ApologyStatus.REJECTED
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    await apology.save()
    
    # Return updated apology with details
    reports, reviews = await get_user_reports_and_reviews(apology.user.id)
    resp = ApologyResponse.model_validate(apology)
    resp.reports = reports
    resp.report_reviews = reviews
    return resp
