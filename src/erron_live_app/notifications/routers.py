from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.notifications.models import NotificationModel
from erron_live_app.notifications.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/",status_code=status.HTTP_200_OK)
async def get_my_notifications(
    limit: int = 50,
    skip: int = 0,
    current_user: UserModel = Depends(get_current_user)
):
    """Get list of notifications."""
    notifications= await NotificationModel.find(
        NotificationModel.user.id == current_user.id
    ).sort("-created_at").limit(limit).skip(skip).to_list()

    unread_message=await NotificationModel.find(
        NotificationModel.user.id == current_user.id,NotificationModel.is_read==False
    ).count()

    return {
        "unread_message":unread_message,
        "notifications":[NotificationResponse(**n.model_dump()) for n in notifications]
    }


@router.patch("/{notification_id}/read", response_model=NotificationResponse,status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: UUID,
    current_user: UserModel = Depends(get_current_user)
):
    """Mark a specific notification as read."""
    notification = await NotificationModel.find_one(
        NotificationModel.id == notification_id,
        NotificationModel.user.id == current_user.id
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notification.is_read = True
    await notification.save()
    return notification


@router.patch("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_read(
    current_user: UserModel = Depends(get_current_user)
):
    """Mark all notifications as read."""
    await NotificationModel.find(
        NotificationModel.user.id == current_user.id,
        NotificationModel.is_read == False
    ).update({"$set": {"is_read": True}})
    
    return {"message": "All marked as read"}
