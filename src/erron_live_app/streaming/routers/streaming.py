import os
import time
from datetime import datetime, timezone
from typing import cast, List
from fastapi import APIRouter, status, HTTPException, Depends, Request
from livekit import api
from dotenv import load_dotenv
from erron_live_app.streaming.models.streaming import LiveStreamModel, LiveViewerModel
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.utils.get_current_user import get_current_user
from erron_live_app.finance.models.transaction import TransactionModel, TransactionType, TransactionReason
from erron_live_app.streaming.models.streaming import LiveCommentModel, LiveLikeModel

load_dotenv()
router = APIRouter(prefix="/streaming", tags=["Livestream"])

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


# --- Helper: LiveKit Token Generator ---
def create_livekit_token(identity: str, name: str, room_name: str, can_publish: bool):
    grant = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(identity) \
        .with_name(name)

    permissions = api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=can_publish,
        can_publish_data=True,
        can_subscribe=True,
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


# --- Endpoints ---

@router.post("/start-stream", status_code=status.HTTP_201_CREATED)
async def start_stream(is_premium: bool, entry_fee: float,title:str,category:str, current_user: UserModel = Depends(get_current_user)):
    """হোস্টের জন্য লাইভ শুরু করার এন্ডপয়েন্ট"""
    if not LIVEKIT_API_KEY:
        raise HTTPException(status_code=500, detail="LiveKit credentials missing")

    # Deduct entry fee from host if premium
    if is_premium and entry_fee > 0:
        if current_user.coins < entry_fee:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, 
                detail=f"Insufficient coins to set entry fee. You need {entry_fee} coins."
            )
        
        current_user.coins -= entry_fee
        await current_user.save()

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

    return {"live_id": str(new_live.id), "livekit_token": token, "channel_name": channel_name}


@router.post("/join-stream/{session_id}")
async def join_stream(session_id: str, current_user: UserModel = Depends(get_current_user)):
    """ভিউয়ারের জন্য জয়েন করার এন্ডপয়েন্ট (কয়েন ট্রানজ্যাকশনসহ)"""
    db_live_stream = await LiveStreamModel.get(session_id, fetch_links=True)

    if not db_live_stream or db_live_stream.status != "live":
        raise HTTPException(status_code=404, detail="Live stream ended")

    host_user = cast(UserModel, db_live_stream.host)

    # Check if user has already joined this session
    existing_viewer = await LiveViewerModel.find_one(
        LiveViewerModel.session.id == db_live_stream.id,
        LiveViewerModel.user.id == current_user.id
    )

    if not existing_viewer:
        # প্রিমিয়াম চেক এবং কয়েন ট্রান্সফার (শুধু প্রথমবার জয়েন করলে)
        if db_live_stream.is_premium and db_live_stream.entry_fee > 0:
            if current_user.coins < db_live_stream.entry_fee:
                raise HTTPException(status_code=402, detail="Insufficient coins")

            current_user.coins -= db_live_stream.entry_fee
            host_user.coins += db_live_stream.entry_fee
            db_live_stream.earn_coins += int(db_live_stream.entry_fee)

            await current_user.save()
            await host_user.save()

            # Log Transactions
            # Debit for Viewer
            await TransactionModel(
                user=current_user.to_ref(),
                amount=db_live_stream.entry_fee,
                transaction_type=TransactionType.DEBIT,
                reason=TransactionReason.ENTRY_FEE_PAID,
                related_entity_id=str(db_live_stream.id),
                description=f"Paid entry fee for stream {db_live_stream.channel_name}"
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

        db_live_stream.total_views += 1
        await db_live_stream.save()

        # Mark user as joined in this session
        await LiveViewerModel(
            session=db_live_stream.to_ref(),
            user=current_user.to_ref(),
            fee_paid=db_live_stream.entry_fee if db_live_stream.is_premium else 0
        ).insert()

    token = create_livekit_token(
        identity=str(current_user.id),
        name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip(),
        room_name=db_live_stream.channel_name,
        can_publish=False
    )

    return {"livekit_token": token, "room_name": db_live_stream.channel_name, "balance": current_user.coins}


@router.post("/stop-stream/{session_id}")
async def stop_stream(session_id: str, current_user: UserModel = Depends(get_current_user)):
    live_session = await LiveStreamModel.get(session_id,fetch_links=True)

    if not live_session or live_session.host.id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not eligible for stop this livestream")

    live_session.status = "ended"
    live_session.end_time = datetime.now(timezone.utc)
    await live_session.save()

    return {"message": "Stream ended successfully"}




@router.get("/active-streams", response_model=List[LiveStreamModel])
async def get_active_streams():
    return await LiveStreamModel.find(LiveStreamModel.status == "live", fetch_links=True).to_list()


@router.get("/active-streams/{category_name}", response_model=List[LiveStreamModel])
async def get_active_category_streams(category_name:str):
    return await LiveStreamModel.find(LiveStreamModel.status == "live",LiveStreamModel.category==category_name, fetch_links=True).to_list()



@router.get("/active-streams/all/free", response_model=List[LiveStreamModel])
async def get_active_free_streams():
    return await LiveStreamModel.find(LiveStreamModel.status == "live",LiveStreamModel.is_premium==False, fetch_links=True).to_list()

@router.get("/active/streams/all/premium", response_model=List[LiveStreamModel])
async def get_active_premium_streams():
    return await LiveStreamModel.find(LiveStreamModel.status == "live",LiveStreamModel.is_premium==True, fetch_links=True).to_list()


@router.get("/all/streams", response_model=List[LiveStreamModel])
async def get_active_streams():
    return await LiveStreamModel.find(fetch_links=True).to_list()






