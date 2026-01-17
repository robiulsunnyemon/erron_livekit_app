import json
import os
import uuid
from typing import List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Request,status
from erron_live_app.users.utils.get_current_user import get_current_user, get_ws_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.chating.models.chat_model import ChatMessageModel
from beanie.operators import Or, And

router = APIRouter(prefix="/chat", tags=["Chat"])

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            await websocket.send_json(message)

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, current_user: UserModel = Depends(get_ws_current_user)):
    user_id = str(current_user.id)
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            receiver_id = message_data.get("receiver_id")
            text = message_data.get("message")
            image_url = message_data.get("image_url")

            if not receiver_id:
                continue

            # Save to Database
            # sender is current_user
            receiver_uuid = UUID(receiver_id)
            receiver = await UserModel.get(receiver_uuid)

            if current_user and receiver:
                chat_msg = ChatMessageModel(
                    sender=current_user.to_ref(),
                    receiver=receiver.to_ref(),
                    message=text,
                    image_url=image_url
                )
                await chat_msg.insert()

                # Prepare payload for real-time delivery
                payload = {
                    "id": str(chat_msg.id),
                    "sender_id": user_id,
                    "receiver_id": receiver_id,
                    "message": text,
                    "image_url": image_url,
                    "created_at": chat_msg.created_at.isoformat()
                }

                # Send to receiver if online
                await manager.send_personal_message(payload, receiver_id)
                # Send back to sender for confirmation
                await manager.send_personal_message(payload, user_id)

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"WebSocket Loop Error: {e}")
        manager.disconnect(user_id)

@router.get("/active-users", response_model=List[UserModel])
async def get_active_users(current_user: UserModel = Depends(get_current_user)):
    """বর্তমানে চ্যাটে এক্টিভ থাকা ইউজারদের তালিকা"""
    active_ids = list(manager.active_connections.keys())
    
    # বর্তমান ইউজারকে বাদ দিয়ে বাকিদের ডাটাবেস থেকে নিয়ে আসা
    # UUID তে কনভার্ট করে Beanie ইন কুয়েরি ব্যবহার করা যায় অথবা লুপ চালানো যায়
    users = []
    for uid in active_ids:
        if uid != str(current_user.id):
            user = await UserModel.get(uuid.UUID(uid))
            if user:
                users.append(user)
    return users

@router.get("/history/{receiver_id}")
async def get_chat_history(receiver_id: str, skip: int = 0, limit: int = 50, current_user: UserModel = Depends(get_current_user)):
    """নির্দিষ্ট ইউজারের সাথে চ্যাট হিস্ট্রি লোড করা"""
    try:
        target_id = UUID(receiver_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid receiver ID")

    messages = await ChatMessageModel.find(
        Or(
            And(ChatMessageModel.sender.id == current_user.id, ChatMessageModel.receiver.id == target_id),
            And(ChatMessageModel.sender.id == target_id, ChatMessageModel.receiver.id == current_user.id)
        ),
        fetch_links=True
    ).sort(-ChatMessageModel.created_at).skip(skip).limit(limit).to_list()
    
    # Return messages in chronological order for the UI
    return messages[::-1]

@router.get("/conversations")
async def get_conversations(current_user: UserModel = Depends(get_current_user)):
    """ইউজারের সব চ্যাট হিস্ট্রি এবং লেটেস্ট মেসেজসহ লিস্ট"""
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"sender.$id": current_user.id},
                    {"receiver.$id": current_user.id}
                ]
            }
        },
        {"$sort": {"created_at": -1}},
        {
            "$group": {
                "_id": {
                    "$cond": [
                        {"$eq": ["$sender.$id", current_user.id]},
                        "$receiver.$id",
                        "$sender.$id"
                    ]
                },
                "last_message": {"$first": "$$ROOT"},
                "unread_count": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$eq": ["$receiver.$id", current_user.id]},
                                {"$eq": ["$is_read", False]}
                            ]},
                            1,
                            0
                        ]
                    }
                }
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user_info"
            }
        },
        {"$unwind": "$user_info"},
        {"$sort": {"last_message.created_at": -1}}
    ]
    
    results = await ChatMessageModel.aggregate(pipeline).to_list()
    
    conversations = []
    for res in results:
        user_info = res["user_info"]
        last_msg = res["last_message"]
        conversations.append({
            "other_user": {
                "id": str(user_info["_id"]),
                "first_name": user_info.get("first_name"),
                "last_name": user_info.get("last_name"),
                "profile_image": user_info.get("profile_image"),
                "is_online": user_info.get("is_online", False)
            },
            "last_message": last_msg.get("message"),
            "last_image_url": last_msg.get("image_url"),
            "created_at": last_msg.get("created_at"),
            "unread_count": res["unread_count"]
        })
            
    return conversations

@router.put("/mark-read/{sender_id}")
async def mark_messages_as_read(sender_id: str, current_user: UserModel = Depends(get_current_user)):
    """নির্দিষ্ট ইউজারের সব মেসেজ 'read' হিসেবে মার্ক করা"""
    try:
        sender_uuid = UUID(sender_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid sender ID")

    await ChatMessageModel.find(
        And(
            ChatMessageModel.sender.id == sender_uuid,
            ChatMessageModel.receiver.id == current_user.id,
            ChatMessageModel.is_read == False
        )
    ).set({ChatMessageModel.is_read: True})
    
    return {"status": "success"}

@router.post("/upload-image")
async def upload_chat_image(request: Request, file: UploadFile = File(...), current_user: UserModel = Depends(get_current_user)):
    """চ্যাটে পাঠানোর জন্য ছবি আপলোড এন্ডপয়েন্ট"""
    file_extension = file.filename.split(".")[-1]
    file_name = f"chat_{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join("uploads", file_name)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Return the full accessible URL

    image_url = f"/uploads/{file_name}"
    return {"image_url": image_url}


@router.delete("all_message",status_code=status.HTTP_200_OK)
async def delete_message():
    await ChatMessageModel.delete_all()
    return {"message":"successfully deleted all message"}