import os
import time
from datetime import datetime, timezone
from typing import cast, List, Union, Optional
from fastapi import APIRouter, status, HTTPException, Depends, Request
from livekit import api
from dotenv import load_dotenv
from instalive_live_app.streaming.models.streaming import LiveStreamModel, LiveViewerModel
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.models.moderator_models import ModeratorModel
from instalive_live_app.users.utils.user_role import UserRole
from instalive_live_app.users.utils.get_current_user import get_current_user
from instalive_live_app.finance.models.transaction import TransactionModel, TransactionType, TransactionReason
from instalive_live_app.streaming.models.streaming import LiveCommentModel, LiveLikeModel
from instalive_live_app.streaming.schemas.streaming import LiveStreamResponse, ActiveStreamsStatsResponse
from instalive_live_app.users.utils.populate_kyc import populate_user_kyc
from instalive_live_app.notifications.utils import send_notification
from instalive_live_app.notifications.models import NotificationType

load_dotenv()
router = APIRouter(prefix="/streaming", tags=["Livestream"])

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


# --- Helper: LiveKit Token Generator ---
def create_livekit_token(identity: str, name: str, room_name: str, can_publish: bool, can_subscribe: bool = True):
    grant = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(name)

    permissions = api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=can_publish,
        can_publish_data=True,
        can_subscribe=can_subscribe,
    )
    grant.with_grants(permissions)
    return grant.to_jwt()


@router.post("/webhook")
async def livekit_webhook(request: Request):
    # নতুন ভার্সনে KeyProvider ব্যবহার করতে হয় অথবা সরাসরি WebhookReceiver এ keys দিতে হয়
    # কিন্তু সবথেকে সহজ উপায় হলো টোকেন ভেরিফাই করা

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=400, detail="Authorization header missing")

    try:
        body = await request.body()
        # সরাসরি API key এবং Secret দিয়ে রিসিভার তৈরি
        receiver = api.WebhookReceiver(
            api.TokenVerifier(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        )

        # ইভেন্ট রিসিভ করা
        event = receiver.receive(body.decode("utf-8"), auth_header)

    except Exception as e:
        print(f"Webhook Error: {e}")
        raise HTTPException(status_code=400, detail="Verification failed")

    # বাকি লজিক আগের মতোই থাকবে
    if event.event == "room_finished":
        room_name = event.room.name
        live_session = await LiveStreamModel.find_one(
            LiveStreamModel.channel_name == room_name,
            LiveStreamModel.status == "live"
        )
        if live_session:
            live_session.status = "ended"
            live_session.end_time = datetime.now(timezone.utc)
            await live_session.save()

    return {"status": "success"}


from instalive_live_app.admin.utils import check_feature_access, log_admin_action

@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_stream(is_premium: bool, entry_fee: float,title:str,category:str, current_user: UserModel = Depends(get_current_user)):
    """হোস্টের জন্য লাইভ শুরু করার এন্ডপয়েন্ট"""
    
    # Emergency Switch Check
    if is_premium:
        await check_feature_access("paid_streams")
        
    if not LIVEKIT_API_KEY:
        raise HTTPException(status_code=500, detail="LiveKit credentials missing")

    # Deduct entry fee from host if premium
    if is_premium and entry_fee > 0:
        if current_user.coins < entry_fee:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, 
                detail=f"Insufficient coins to set entry fee. You need {entry_fee} coins."
            )
        
        # Atomic decrement
        await current_user.update({"$inc": {UserModel.coins: -int(entry_fee)}})
        # Fetch updated user to ensure local object is sane (optional but good)
        await current_user.fetch()

    channel_name = f"live_{current_user.id}_{int(time.time())}"
    token = create_livekit_token(
        identity=str(current_user.id),
        name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip(),
        room_name=channel_name,
        can_publish=True
    )

    new_live = LiveStreamModel(
        host=current_user.to_ref(),
        channel_name=channel_name,
        livekit_token=token,
        is_premium=is_premium,
        entry_fee=entry_fee if is_premium else 0,
        status="live",
        title=title,
        category=category,
        thumbnail=current_user.profile_image
    )
    await new_live.insert()

    # Log Transaction for Host
    if is_premium and entry_fee > 0:
        await TransactionModel(
            user=current_user.to_ref(),
            amount=entry_fee,
            transaction_type=TransactionType.DEBIT,
            reason=TransactionReason.HOST_STREAM_FEE_PAID,
            related_entity_id=str(new_live.id),
            description=f"Paid fee to start premium stream with {entry_fee} entry fee"
        ).insert()

    # Notification: Live Started
    await send_notification(
        user=current_user,
        title="Live Started",
        body=f"You started a live stream: {title}",
        type=NotificationType.LIVE,
        related_entity_id=str(new_live.id)
    )

    return {
        "live_id": str(new_live.id), 
        "livekit_token": token, 
        "channel_name": channel_name,
        "is_premium": is_premium,
        "entry_fee": entry_fee if is_premium else 0
    }


@router.post("/join/{session_id}")
async def join_stream(session_id: str, request: Request):
    """ভিউয়ারের জন্য জয়েন করার এন্ডপয়েন্ট (কয়েন ট্রানজ্যাকশনসহ) - গেস্ট এলাউড"""
    
    # টোকেন থেকে ইউজার বের করার চেষ্টা করা
    current_user = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            from instalive_live_app.users.utils.get_current_user import verify_token
            current_user = await verify_token(token)
        except Exception:
            current_user = None

    db_live_stream = await LiveStreamModel.get(session_id, fetch_links=True)

    if not db_live_stream or db_live_stream.status != "live":
        raise HTTPException(status_code=404, detail="Live stream ended")

    # Determine initial has_paid status
    has_paid = not db_live_stream.is_premium

    if current_user:
        # মাস্ট রেজিস্টার্ড ইউজারদের জন্য ভিউ রেকর্ড আপডেট
        existing_viewer = await LiveViewerModel.find_one(
            LiveViewerModel.session.id == db_live_stream.id,
            LiveViewerModel.user.id == current_user.id
        )

        is_admin = current_user.role == UserRole.ADMIN
        # Moderator check
        is_moderator = False # Assume false or fetch as per original logic

        if is_admin: has_paid = True

        if not existing_viewer:
            db_live_stream.total_views += 1
            await db_live_stream.save()

            await LiveViewerModel(
                session=db_live_stream.to_ref(),
                user=current_user.to_ref(),
                fee_paid=0,
                has_paid=has_paid
            ).insert()
        else:
            has_paid = has_paid or existing_viewer.has_paid or is_admin
        
        identity = str(current_user.id)
        name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or "User"
    else:
        # গেস্ট ইউজার লজিক
        identity = f"guest_{int(time.time())}"
        name = "Guest User"
        has_paid = False # গেস্টদের জন্য প্রিমিয়াম স্ট্রিমে সবসময় পে করতে হবে (যা তারা পারবে না, তাই ব্লার থাকবে)
        if not db_live_stream.is_premium:
            has_paid = True # ফ্রি স্ট্রিম হলে গেস্টদের জন্যও পেইড (ব্লার হবে না)

    token = create_livekit_token(
        identity=identity,
        name=name,
        room_name=db_live_stream.channel_name,
        can_publish=False,
        can_subscribe=has_paid # Server-side gating: restrict subscription if not paid
    )

    return {
        "livekit_token": token, 
        "room_name": db_live_stream.channel_name, 
        "balance": current_user.coins if current_user else 0,
        "is_premium": db_live_stream.is_premium,
        "has_paid": has_paid,
        "entry_fee": db_live_stream.entry_fee
    }


@router.post("/pay/{session_id}")
async def pay_stream_fee(session_id: str, current_user: UserModel = Depends(get_current_user)):
    """
    Endpoint for paying the stream fee after the 3-second free preview.
    """
    db_live_stream = await LiveStreamModel.get(session_id, fetch_links=True)
    if not db_live_stream or db_live_stream.status != "live":
        raise HTTPException(status_code=404, detail="Live stream ended or not found")

    host_user = cast(UserModel, db_live_stream.host)

    # Find viewer record
    viewer_record = await LiveViewerModel.find_one(
        LiveViewerModel.session.id == db_live_stream.id,
        LiveViewerModel.user.id == current_user.id
    )

    if not viewer_record:
        raise HTTPException(status_code=400, detail="You must join the stream first")

    if viewer_record.has_paid:
        return {"message": "Already paid", "balance": current_user.coins}

    if not db_live_stream.is_premium or db_live_stream.entry_fee <= 0:
         # Should be paid/free anyway
         viewer_record.has_paid = True
         await viewer_record.save()
         return {"message": "Stream is free", "balance": current_user.coins}

    # Process Payment: Atomic updates
    if current_user.coins < db_live_stream.entry_fee:
        raise HTTPException(status_code=402, detail="Insufficient coins")

    await current_user.update({"$inc": {UserModel.coins: -int(db_live_stream.entry_fee)}})
    await host_user.update({"$inc": {UserModel.coins: int(db_live_stream.entry_fee)}})
    
    # Update stream earnings - also should be atomic if possible, but stream object is smaller risk
    await db_live_stream.update({"$inc": {LiveStreamModel.earn_coins: int(db_live_stream.entry_fee)}})

    # Refresh local objects
    await current_user.fetch()
    await host_user.fetch()
    await db_live_stream.fetch()

    # Log Transactions
    # Debit for Viewer
    await TransactionModel(
        user=current_user.to_ref(),
        amount=db_live_stream.entry_fee,
        transaction_type=TransactionType.DEBIT,
        reason=TransactionReason.ENTRY_FEE_PAID,
        related_entity_id=str(db_live_stream.id),
        description=f"Paid entry fee for stream {db_live_stream.channel_name} (After Preview)"
    ).insert()

    # Credit for Host
    await TransactionModel(
        user=host_user.to_ref(),
        amount=db_live_stream.entry_fee,
        transaction_type=TransactionType.CREDIT,
        reason=TransactionReason.ENTRY_FEE_RECEIVED,
        related_entity_id=str(db_live_stream.id),
        description=f"Received entry fee from {current_user.first_name}"
    ).insert()

    # Update Viewer Record
    viewer_record.has_paid = True
    await viewer_record.save()

    # Issue NEW token with can_subscribe=True
    new_token = create_livekit_token(
        identity=str(current_user.id),
        name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or "User",
        room_name=db_live_stream.channel_name,
        can_publish=False,
        can_subscribe=True
    )

    return {
        "message": "Payment successful",
        "livekit_token": new_token,
        "balance": current_user.coins
    }
    viewer_record.fee_paid = db_live_stream.entry_fee
    await viewer_record.save()

    return {"message": "Payment successful", "balance": current_user.coins}


@router.post("/stop/{session_id}")
async def stop_stream(session_id: str, current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)):
    live_session = await LiveStreamModel.get(session_id, fetch_links=True)

    if not live_session:
        raise HTTPException(status_code=404, detail="Live stream not found")
    
    # Check permissions: Host, Admin, or Moderator
    is_host = isinstance(current_user, UserModel) and live_session.host.id == current_user.id
    is_admin = isinstance(current_user, UserModel) and current_user.role == UserRole.ADMIN
    is_moderator = isinstance(current_user, ModeratorModel)
    
    if not (is_host or is_admin or is_moderator):
        raise HTTPException(status_code=403, detail="You are not authorized to stop this livestream")

    live_session.status = "ended"
    live_session.end_time = datetime.now(timezone.utc)
    await live_session.save()

    # Log specific admin/mod actions
    if is_admin or is_moderator:
        await log_admin_action(
            actor=current_user,
            action="Stopped Live Stream",
            target=str(live_session.id),
            severity="Medium",
            details=f"Forcefully stopped stream {live_session.channel_name}"
        )

    # Notification: Live Ended
    # We send to host (if they didn't stop it themselves? OR just a summary)
    if live_session.host:
        host_user = live_session.host
        if host_user:
            await send_notification(
                user=host_user,
                title="Live Ended",
                body=f"Your live stream has ended.",
                type=NotificationType.LIVE,
                related_entity_id=str(live_session.id)
            )

    return {"message": "Stream ended successfully"}


@router.put("/resume/{session_id}")
async def resume_stream(session_id: str, current_user: Union[UserModel, ModeratorModel] = Depends(get_current_user)):
    live_session = await LiveStreamModel.get(session_id, fetch_links=True)

    if not live_session:
        raise HTTPException(status_code=404, detail="Live stream not found")

    # Check permissions: Host, Admin, or Moderator
    is_host = isinstance(current_user, UserModel) and live_session.host.id == current_user.id
    is_admin = isinstance(current_user, UserModel) and current_user.role == UserRole.ADMIN
    is_moderator = isinstance(current_user, ModeratorModel)

    if not (is_host or is_admin or is_moderator):
        raise HTTPException(status_code=403, detail="You are not authorized to stop this livestream")

    live_session.status = "live"
    live_session.end_time = None
    await live_session.save()
    
    # Log specific admin/mod actions
    if is_admin or is_moderator:
        await log_admin_action(
            actor=current_user,
            action="Resumed Live Stream",
            target=str(live_session.id),
            severity="Medium",
            details=f"Forcefully resumed stream {live_session.channel_name}"
        )

    return {"message": "Stream resumed successfully"}




@router.get("/active", response_model=List[LiveStreamResponse])
async def get_active_streams():
    streams = await LiveStreamModel.find(LiveStreamModel.status == "live", fetch_links=True).sort("-created_at").to_list()
    
    # Populate KYC for each host
    streams_with_kyc = []
    for stream in streams:
        stream_dict = stream.model_dump()
        if stream.host:
            host_with_kyc = await populate_user_kyc(stream.host)
            stream_dict["host"] = host_with_kyc
        streams_with_kyc.append(stream_dict)
    
    return streams_with_kyc


@router.get("/active/{category_name}", response_model=List[LiveStreamResponse])
async def get_active_category_streams(category_name:str):
    streams = await LiveStreamModel.find(LiveStreamModel.status == "live",LiveStreamModel.category==category_name, fetch_links=True).to_list()
    
    # Populate KYC for each host
    streams_with_kyc = []
    for stream in streams:
        stream_dict = stream.model_dump()
        if stream.host:
            host_with_kyc = await populate_user_kyc(stream.host)
            stream_dict["host"] = host_with_kyc
        streams_with_kyc.append(stream_dict)
    
    return streams_with_kyc



@router.get("/active/all/free", response_model=List[LiveStreamResponse])
async def get_active_free_streams():
    streams = await LiveStreamModel.find(LiveStreamModel.status == "live",LiveStreamModel.is_premium==False, fetch_links=True).to_list()
    
    # Populate KYC for each host
    streams_with_kyc = []
    for stream in streams:
        stream_dict = stream.model_dump()
        if stream.host:
            host_with_kyc = await populate_user_kyc(stream.host)
            stream_dict["host"] = host_with_kyc
        streams_with_kyc.append(stream_dict)
    
    return streams_with_kyc

@router.get("/active/streams/all/premium", response_model=List[LiveStreamResponse])
async def get_active_premium_streams():
    streams = await LiveStreamModel.find(LiveStreamModel.status == "live",LiveStreamModel.is_premium==True, fetch_links=True).to_list()
    
    # Populate KYC for each host
    streams_with_kyc = []
    for stream in streams:
        stream_dict = stream.model_dump()
        if stream.host:
            host_with_kyc = await populate_user_kyc(stream.host)
            stream_dict["host"] = host_with_kyc
        streams_with_kyc.append(stream_dict)
    
    return streams_with_kyc


@router.get("/all/streams", response_model=List[LiveStreamResponse])
async def get_active_streams():
    streams = await LiveStreamModel.find(fetch_links=True).to_list()
    
    # Populate KYC for each host
    streams_with_kyc = []
    for stream in streams:
        stream_dict = stream.model_dump()
        if stream.host:
            host_with_kyc = await populate_user_kyc(stream.host)
            stream_dict["host"] = host_with_kyc
        streams_with_kyc.append(stream_dict)
    
    return streams_with_kyc


@router.get("/stats/active-streams", response_model=ActiveStreamsStatsResponse)
async def get_active_streams_stats():
    total = await LiveStreamModel.find(LiveStreamModel.status == "live").count()
    free = await LiveStreamModel.find(
        LiveStreamModel.status == "live",
        LiveStreamModel.is_premium == False
    ).count()
    paid = await LiveStreamModel.find(
        LiveStreamModel.status == "live",
        LiveStreamModel.is_premium == True
    ).count()

    return {
        "total": total,
        "free": free,
        "paid": paid
    }
@router.get("/search", response_model=List[LiveStreamResponse])
async def search_streams(q: str):
    """
    হোস্টের নাম, টাইটেল, চ্যানেল নাম এবং ক্যাটাগরি অনুযায়ী সার্চ করার এন্ডপয়েন্ট।
    """
    pipeline = [
        {"$match": {"status": "live"}},
        {
            "$lookup": {
                "from": "users",
                "localField": "host.$id",
                "foreignField": "_id",
                "as": "host_info"
            }
        },
        {"$unwind": "$host_info"},
        {
            "$match": {
                "$or": [
                    {"title": {"$regex": q, "$options": "i"}},
                    {"category": {"$regex": q, "$options": "i"}},
                    {"channel_name": {"$regex": q, "$options": "i"}},
                    {"host_info.first_name": {"$regex": q, "$options": "i"}},
                    {"host_info.last_name": {"$regex": q, "$options": "i"}}
                ]
            }
        },
        {"$sort": {"created_at": -1}}
    ]
    
    results = await LiveStreamModel.aggregate(pipeline).to_list()
    
    # LiveStreamResponse এর সাথে মিল রাখার জন্য এবং KYC পপুলেট করার জন্য
    # রেজাল্টগুলো ম্যানুয়ালি প্রসেস করা হচ্ছে
    streams_with_kyc = []
    for res in results:
        # DB ID কে স্ট্রিং হিসেবে এবং _id কে id হিসেবে সেট করা
        res["id"] = res["_id"]
        
        # KYC পপুলেশন
        host_info = res.get("host_info")
        if host_info:
            # We need a UserModel object for populate_user_kyc
            # Minimally converting host_info to something the helper can use
            # Or just fetch user again for safety
            user = await UserModel.get(host_info["_id"])
            if user:
                res["host"] = await populate_user_kyc(user)
        
        streams_with_kyc.append(res)
        
    return streams_with_kyc


@router.get("/lottery/{session_id}")
async def run_lottery(session_id: str, current_user: UserModel = Depends(get_current_user)):
    """
    Select a random viewer from the current live stream.
    Only the host or an admin/moderator can trigger this.
    """
    live_session = await LiveStreamModel.get(session_id, fetch_links=True)
    if not live_session or live_session.status != "live":
        raise HTTPException(status_code=404, detail="Active live stream not found")

    # Permissions
    is_host = live_session.host.id == current_user.id
    is_staff = current_user.role in [UserRole.ADMIN, UserRole.MODERATOR] # Check if ROLE exists
    
    if not is_host and not is_staff:
         raise HTTPException(status_code=403, detail="Permission denied")

    # Fetch viewers
    import random
    viewers = await LiveViewerModel.find(LiveViewerModel.session.id == live_session.id, fetch_links=True).to_list()
    
    if not viewers:
        return {"message": "No viewers found to run lottery"}

    winner_record = random.choice(viewers)
    winner_user = winner_record.user
    
    # Optional: Send notification to winner
    await send_notification(
        user=winner_user,
        title="🎉 Lottery Winner!",
        body=f"Congratulations! You've been selected as the winner in {live_session.title}.",
        type=NotificationType.ACCOUNT
    )

    return {
        "status": "success",
        "winner": {
            "id": str(winner_user.id),
            "name": f"{winner_user.first_name or ''} {winner_user.last_name or ''}".strip(),
            "profile_image": winner_user.profile_image
        }
    }
