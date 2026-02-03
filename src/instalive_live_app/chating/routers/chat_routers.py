import json
import os
import uuid
import asyncio
import logging
from typing import List, Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Request, status
from instalive_live_app.users.utils.get_current_user import get_current_user, get_ws_current_user
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.schemas.user_schemas import UserResponse
from instalive_live_app.chating.models.chat_model import ChatMessageModel
from instalive_live_app.chating.schemas.chat import ChatMessageResponse, ConversationResponse
from instalive_live_app.users.utils.populate_kyc import populate_user_kyc
from beanie.operators import Or, And
import redis.asyncio as redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

router = APIRouter(prefix="/chat", tags=["Chat"])

# WebSocket Connection Manager with Redis Pub/Sub
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.redis: Optional[redis.Redis] = None
        self.pubsub_task: Optional[asyncio.Task] = None

    async def ensure_redis(self):
        if not self.redis:
            try:
                self.redis = redis.from_url(REDIS_URL, decode_responses=True)
                # Test connection
                await self.redis.ping()
                self.pubsub_task = asyncio.create_task(self._listen_to_redis())
                logger.info("Connected to Redis for Chat Pub/Sub")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Falling back to local-only chat.")
                self.redis = None

    async def _listen_to_redis(self):
        ps = self.redis.pubsub()
        await ps.subscribe("chat_updates")
        try:
            async for message in ps.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    receiver_id = data.get("receiver_id")
                    if receiver_id in self.active_connections:
                        await self.active_connections[receiver_id].send_json(data)
        except Exception as e:
            logger.error(f"Redis PubSub Error: {e}")
        finally:
            await ps.unsubscribe("chat_updates")

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        await self.ensure_redis()

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def broadcast_to_redis(self, message: dict):
        if self.redis:
            await self.redis.publish("chat_updates", json.dumps(message))
        else:
            # Fallback for local-only if Redis is missing
            receiver_id = message.get("receiver_id")
            # If we are in local mode, we need to send to the target receiver
            if receiver_id in self.active_connections:
                try:
                    await self.active_connections[receiver_id].send_json(message)
                except Exception as e:
                    logger.error(f"Local Send Error: {e}")

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, current_user: UserModel = Depends(get_ws_current_user)):
    user_id = str(current_user.id)
    await manager.connect(user_id, websocket)
    
    # Heartbeat task
    async def heartbeat():
        try:
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "ping"})
        except Exception:
            pass

    heartbeat_task = asyncio.create_task(heartbeat())
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            msg_type = message_data.get("type", "message")
            
            if msg_type == "pong":
                continue
                
            receiver_id = message_data.get("receiver_id")
            if not receiver_id:
                continue

            if msg_type == "message":
                text = message_data.get("message")
                image_url = message_data.get("image_url")
                replied_to_id = message_data.get("replied_to_id")

                # Save to Database
                receiver_uuid = UUID(receiver_id)
                receiver = await UserModel.get(receiver_uuid)

                if current_user and receiver:
                    replied_to_uuid = None
                    if replied_to_id:
                        try:
                            replied_to_uuid = UUID(replied_to_id)
                        except (ValueError, TypeError):
                            pass

                    chat_msg = ChatMessageModel(
                        sender=current_user.to_ref(),
                        receiver=receiver.to_ref(),
                        message=text,
                        image_url=image_url,
                        replied_to_id=replied_to_uuid
                    )
                    await chat_msg.insert()

                    # Prepare payload for real-time delivery
                    payload = {
                        "type": "message",
                        "id": str(chat_msg.id),
                        "sender_id": user_id,
                        "receiver_id": receiver_id,
                        "message": text,
                        "image_url": image_url,
                        "replied_to_id": str(chat_msg.replied_to_id) if chat_msg.replied_to_id else None,
                        "created_at": chat_msg.created_at.isoformat(),
                        "reactions": []
                    }

                    # Broadcast via Redis (handles multi-instance)
                    await manager.broadcast_to_redis(payload)
                    # Also notify sender (this handles them whether they are on this instance or not)
                    # However, broadcast_to_redis already sends it to the receiver_id.
                    # We might need to send to sender too if they are on a different instance.
                    await manager.broadcast_to_redis({**payload, "receiver_id": user_id})

            elif msg_type == "reaction":
                message_id = message_data.get("message_id")
                emoji = message_data.get("emoji")
                
                if not message_id or not emoji:
                    continue
                
                chat_msg = await ChatMessageModel.get(message_id)
                if chat_msg:
                    # Remove existing reaction from this user if any
                    chat_msg.reactions = [r for r in chat_msg.reactions if r.user_id != user_id]
                    # Add new reaction
                    from instalive_live_app.chating.models.chat_model import Reaction
                    chat_msg.reactions.append(Reaction(user_id=user_id, emoji=emoji))
                    await chat_msg.save()

                    payload = {
                        "type": "reaction",
                        "message_id": message_id,
                        "user_id": user_id,
                        "emoji": emoji,
                        "receiver_id": receiver_id # To identify which room to broadcast in
                    }
                    
                    await manager.broadcast_to_redis(payload)
                    await manager.broadcast_to_redis({**payload, "receiver_id": user_id})

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket Loop Error for user {user_id}: {e}")
        manager.disconnect(user_id)
    finally:
        heartbeat_task.cancel()

@router.get("/active-users", response_model=List[UserResponse])
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

@router.get("/history/{receiver_id}", response_model=List[ChatMessageResponse])
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
    
    # Populate KYC for sender and receiver
    messages_with_kyc = []
    for message in messages:
        msg_dict = message.model_dump()
        if message.sender:
            sender_with_kyc = await populate_user_kyc(message.sender)
            msg_dict["sender"] = sender_with_kyc
        if message.receiver:
            receiver_with_kyc = await populate_user_kyc(message.receiver)
            msg_dict["receiver"] = receiver_with_kyc
        messages_with_kyc.append(msg_dict)
    
    # Return messages in chronological order for the UI
    return messages_with_kyc[::-1]

@router.get("/conversations", response_model=List[ConversationResponse])
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


# @router.delete("all_message",status_code=status.HTTP_200_OK)
# async def delete_message():
#     await ChatMessageModel.delete_all()
#     return {"message":"successfully deleted all message"}
