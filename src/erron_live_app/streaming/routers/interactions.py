from fastapi import APIRouter, Depends, HTTPException,status
from watchfiles import awatch

from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.streaming.models.streaming import LiveStreamModel, LiveLikeModel, LiveCommentModel, LiveRatingModel, \
    LiveViewerModel, LiveStreamReportModel

router = APIRouter(prefix="/streaming/interactions", tags=["Interactions"])

@router.post("/like")
async def like_stream(session_id: str, current_user: UserModel = Depends(get_current_user)):
    stream = await LiveStreamModel.get(session_id)
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    # Check if already liked? (Optional, skipping for now to allow multiple taps like TikTok/Bigo)
    await LiveLikeModel(
        session=stream.to_ref(),
        user=current_user.to_ref()
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
        session=stream.to_ref(),
        user=current_user.to_ref(),
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
    current_user: UserModel = Depends(get_current_user)
):
    stream = await LiveStreamModel.get(session_id)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")

    await LiveStreamReportModel(
        session=stream.to_ref(),
        reporter=current_user.to_ref(),
        category=category,
        description=description
    ).insert()

    return {"status": "reported"}

@router.get("/report",status_code=status.HTTP_200_OK)
async def get_all_report():
    reports=await LiveStreamReportModel.find_all().to_list()
    return reports





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
