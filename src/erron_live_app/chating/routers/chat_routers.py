import json
import os
import uuid
from typing import List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.chating.models.chat_model import ChatMessageModel
from beanie import Link
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

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    try:
        # Verify the user_id is a valid UUID
        current_user_uuid = UUID(user_id)
        
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
                sender = await UserModel.get(current_user_uuid)
                receiver = await UserModel.get(UUID(receiver_id))

                if sender and receiver:
                    chat_msg = ChatMessageModel(
                        sender=sender.to_ref(),
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
            
    except Exception as e:
        print(f"WebSocket Connect Error: {e}")
        await websocket.close(code=1008)

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

@router.post("/upload-image")
async def upload_chat_image(request: Request, file: UploadFile = File(...), current_user: UserModel = Depends(get_current_user)):
    """চ্যাটে পাঠানোর জন্য ছবি আপলোড এন্ডপয়েন্ট"""
    file_extension = file.filename.split(".")[-1]
    file_name = f"chat_{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join("uploads", file_name)

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Return the full accessible URL
    base_url = str(request.base_url)
    image_url = f"{base_url}uploads/{file_name}"
    return {"image_url": image_url}
