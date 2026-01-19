from fastapi import APIRouter, Depends, HTTPException, status
from erron_live_app.users.schemas.user_schemas import UserResponse, ProfileResponse, ModeratorProfileResponse, ReportReviewRequest, ReportReviewResponse
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.models.moderator_models import ModeratorModel
from erron_live_app.users.utils.account_status import AccountStatus
from erron_live_app.users.utils.user_role import UserRole
from typing import Union, Optional
from uuid import UUID
from erron_live_app.streaming.models.streaming import LiveStreamModel, LiveLikeModel, LiveCommentModel, LiveRatingModel, \
    LiveViewerModel, LiveStreamReportModel, LiveStreamReportReviewModel

router = APIRouter(prefix="/streaming/interactions", tags=["Interactions"])

@router.post("/like")
async def like_stream(session_id: str, current_user: UserModel = Depends(get_current_user)):
    stream = await LiveStreamModel.get(session_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    # Check if already liked? (Optional, skipping for now to allow multiple taps like TikTok/Bigo)
    await LiveLikeModel(
        session=stream,
        user=current_user
    ).insert()
    
    stream.total_likes += 1
    await stream.save()
    
    return {"user":current_user,"status": "liked", "total_likes": stream.total_likes}

@router.post("/comment",status_code=status.HTTP_201_CREATED)
async def comment_stream(session_id: str, content: str, current_user: UserModel = Depends(get_current_user)):
    stream = await LiveStreamModel.get(session_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")

    await LiveCommentModel(
        session=stream,
        user=current_user,
        content=content
    ).insert()

    stream.total_comments += 1
    await stream.save()

    return {
        "user":current_user,
        "content":content
    }



@router.post("/report",status_code=status.HTTP_201_CREATED)
async def report_stream(
    session_id: str, 
    category: str, 
    description: str = None, 
    current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
):
    stream = await LiveStreamModel.get(session_id)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")

    report = LiveStreamReportModel(
        session=stream,
        category=category,
        description=description
    )

    if isinstance(current_user, ModeratorModel):
        report.reporter_moderator = current_user
        current_user.reported_count += 1
        await current_user.save()
    else:
        report.reporter_user = current_user

    await report.insert()

    return {"status": "reported"}

@router.get("/report",status_code=status.HTTP_200_OK)
async def get_all_report(status: Optional[str] = None):
    query = {}
    if status and status != "All":
        query = {"status": status}
    
    reports = await LiveStreamReportModel.find(query, fetch_links=True).to_list()
    return reports


@router.post("/report/{report_id}/review", response_model=ReportReviewResponse)
async def review_report(
    report_id: UUID, 
    data: ReportReviewRequest, 
    current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)
):
    # Permission Check: Only Admins or Moderators with can_review_appeals/can_manage_users
    is_admin = isinstance(current_user, UserModel) and current_user.role == UserRole.ADMIN
    is_allowed_mod = isinstance(current_user, ModeratorModel) and (current_user.can_view_reports or current_user.can_review_appeals or current_user.can_manage_users)
    
    if not is_admin and not is_allowed_mod:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    # Find the report
    report = await LiveStreamReportModel.get(report_id, fetch_links=True)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # Create the review record
    review = LiveStreamReportReviewModel(
        report=report,
        moderator=current_user,
        note=data.note,
        action=data.action
    )
    await review.insert()

    # Update report status
    if data.action == "DISMISS":
        report.status = "DISMISSED"
    else:
        report.status = "RESOLVED"
    await report.save()

    # Execute Action on the Host (Target User)
    if data.action in ["SUSPEND", "INACTIVE"]:
        host = report.session.host
        if hasattr(host, "fetch"):
            host = await host.fetch()
        if host:
            if data.action == "SUSPEND":
                host.account_status = AccountStatus.SUSPEND
                if isinstance(current_user, ModeratorModel):
                    current_user.suspended_count += 1
            elif data.action == "INACTIVE":
                host.account_status = AccountStatus.INACTIVE
                if isinstance(current_user, ModeratorModel):
                    current_user.inactivated_count += 1
            
            await host.save()
            if isinstance(current_user, ModeratorModel):
                await current_user.save()

    return {
        "id": review.id,
        "report_id": report.id,
        "moderator_id": current_user.id,
        "note": review.note,
        "action": review.action,
        "created_at": review.created_at
    }





@router.get("/all/comment", status_code=status.HTTP_200_OK)
async def get_all_comment():
    return await LiveCommentModel.find(fetch_links=True).to_list()

@router.delete("/delete/all/comment", status_code=status.HTTP_200_OK)
async def delete_all_comment():
    await LiveCommentModel.delete_all()
    return {"message": "successfully deleted all comments"}


@router.get("/all/viewers", status_code=status.HTTP_200_OK)
async def get_all_comment():
    return await LiveViewerModel.find(fetch_links=True).to_list()

@router.delete("/delete/all/viewers", status_code=status.HTTP_200_OK)
async def delete_all_viewers():
    await LiveViewerModel.delete_all()
    return {"message": "successfully deleted all viewers"}

@router.get("/all/likes",status_code=status.HTTP_200_OK)
async def get_all_likes():
    return await LiveLikeModel.find(fetch_links=True).to_list()

@router.delete("/delete/all/likes", status_code=status.HTTP_200_OK)
async def delete_all_likes():
    await LiveLikeModel.delete_all()
    return {"message": "successfully deleted all likes"}


@router.delete("/delete/all/live",status_code=status.HTTP_200_OK)
async def delete_all_livestream():
    await LiveStreamModel.delete_all()
    return {"message":"successfully deleted all livestream"}
