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

load_dotenv()
router = APIRouter(prefix="/streaming", tags=["Live Stream"])

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
    # নতুন ভার্সনে শুধু secret দিয়ে রিসিভার তৈরি করতে হয় অথবা সরাসরি ভেরিফাই করতে হয়
    receiver = api.WebhookReceiver(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)

    try:
        body = await request.body()
        auth_header = request.headers.get("Authorization")
        # এটি এখন ইভেন্ট অবজেক্ট রিটার্ন করবে
        event = receiver.receive(body.decode("utf-8"), auth_header)
    except Exception as e:
        print(f"Webhook Error: {e}")
        raise HTTPException(status_code=400, detail="ভেরিফিকেশন ব্যর্থ হয়েছে")

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
async def start_stream(is_premium: bool, entry_fee: float, current_user: UserModel = Depends(get_current_user)):
    """হোস্টের জন্য লাইভ শুরু করার এন্ডপয়েন্ট"""
    if not LIVEKIT_API_KEY:
        raise HTTPException(status_code=500, detail="LiveKit credentials missing")

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
        status="live"
    )
    await new_live.insert()

    return {"live_id": str(new_live.id), "livekit_token": token, "channel_name": channel_name}


@router.post("/join-stream/{session_id}")
async def join_stream(session_id: str, current_user: UserModel = Depends(get_current_user)):
    """ভিউয়ারের জন্য জয়েন করার এন্ডপয়েন্ট (কয়েন ট্রানজ্যাকশনসহ)"""
    db_live_stream = await LiveStreamModel.get(session_id, fetch_links=True)

    if not db_live_stream or db_live_stream.status != "live":
        raise HTTPException(status_code=404, detail="Live stream ended")

    host_user = cast(UserModel, db_live_stream.host)

    # প্রিমিয়াম চেক এবং কয়েন ট্রান্সফার
    if db_live_stream.is_premium:
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

    token = create_livekit_token(
        identity=str(current_user.id),
        name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip(),
        room_name=db_live_stream.channel_name,
        can_publish=False
    )

    db_live_stream.total_views += 1
    await db_live_stream.save()

    await LiveViewerModel(
        session=db_live_stream.to_ref(),
        user=current_user.to_ref(),
        fee_paid=db_live_stream.entry_fee if db_live_stream.is_premium else 0
    ).insert()

    return {"livekit_token": token, "room_name": db_live_stream.channel_name, "balance": current_user.coins}


@router.get("/active-streams", response_model=List[LiveStreamModel])
async def get_active_streams():
    return await LiveStreamModel.find(LiveStreamModel.status == "live", fetch_links=True).to_list()


@router.delete("/delete/all/live",status_code=status.HTTP_200_OK)
async def delete_all_livestream():
    await LiveStreamModel.delete_all()
    return {"message":"successfully deleted all livestream"}





