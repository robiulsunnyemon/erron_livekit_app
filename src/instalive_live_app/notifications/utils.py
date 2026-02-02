from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.notifications.models import NotificationModel, NotificationType

async def send_notification(
    user: UserModel, 
    title: str, 
    body: str, 
    type: NotificationType, 
    related_entity_id: str = None
):
    """
    Centralized function to send notifications.
    Currently saves to DB. Can be extended to Push/Socket.
    """
    notification = NotificationModel(
        user=user.to_ref(),
        title=title,
        body=body,
        type=type,
        related_entity_id=related_entity_id
    )
    await notification.insert()
    
    # Future: Trigger Socket.IO event here
    # await sio.emit("notification", notification.model_dump(), room=str(user.id))
    
    return notification
