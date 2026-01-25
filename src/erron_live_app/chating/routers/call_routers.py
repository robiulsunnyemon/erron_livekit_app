from fastapi import APIRouter, Depends, HTTPException, status
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.chating.routers.chat_routers import manager
from erron_live_app.streaming.routers.streaming import create_livekit_token
import uuid

router = APIRouter(prefix="/chat/call", tags=["Chat Call"])

@router.post("/initiate")
async def initiate_call(receiver_id: str, call_type: str, current_user: UserModel = Depends(get_current_user)):
    """
    শুরু (Initiation): কলার কল শুরু করার জন্য এই এন্ডপয়েন্ট কল করবে।
    রিিসিভারের ওয়েবসকেটে 'call_incoming' ইভেন্ট পাঠানো হবে।
    """
    room_name = f"call_{uuid.uuid4()}"
    token = create_livekit_token(
        identity=str(current_user.id),
        name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or "User",
        room_name=room_name,
        can_publish=True
    )

    # Signaling payload
    payload = {
        "type": "call_incoming",
        "caller_id": str(current_user.id),
        "caller_name": f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or "Someone",
        "caller_image": current_user.profile_image,
        "room_name": room_name,
        "call_type": call_type # "audio" or "video"
    }

    # Send signal to receiver via WebSocket
    await manager.send_personal_message(payload, receiver_id)

    return {"room_name": room_name, "token": token}

@router.post("/respond")
async def respond_to_call(room_name: str, caller_id: str, action: str, current_user: UserModel = Depends(get_current_user)):
    """
    রেসপন্স (Response): রিিসিভার কল এক্সেপ্ট বা রিজেক্ট করলে এই এন্ডপয়েন্ট কল করবে।
    """
    if action == "accept":
        token = create_livekit_token(
            identity=str(current_user.id),
            name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or "User",
            room_name=room_name,
            can_publish=True
        )
        # Notify caller that the call was accepted
        payload = {
            "type": "call_accepted",
            "receiver_id": str(current_user.id),
            "room_name": room_name
        }
        await manager.send_personal_message(payload, caller_id)
        return {"token": token}
    else:
        # Notify caller that the call was rejected
        payload = {
            "type": "call_rejected",
            "receiver_id": str(current_user.id),
            "room_name": room_name
        }
        await manager.send_personal_message(payload, caller_id)
        return {"status": "rejected"}

@router.post("/end")
async def end_call(other_user_id: str, room_name: str = "", current_user: UserModel = Depends(get_current_user)):
    """
    কল শেষ করা (End Call): যেকোনো পক্ষ কল শেষ করলে সিগনাল পাঠাবে।
    """
    payload = {
        "type": "call_ended",
        "room_name": room_name
    }
    await manager.send_personal_message(payload, other_user_id)
    return {"status": "success"}
