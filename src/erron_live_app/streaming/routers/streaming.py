import os
import time
from dotenv import load_dotenv
from fastapi import APIRouter,status,HTTPException,Depends
from livekit import api
from erron_live_app.streaming.models.streaming import LiveStreamModel
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.users.utils.get_current_user import get_current_user

load_dotenv()
router = APIRouter(prefix="/streaming",tags=["Live Stream"])


LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


@router.post("/get-token",status_code=status.HTTP_201_CREATED)
async def get_token(is_premium:bool,entry_fee:float,current_user: UserModel = Depends(get_current_user)):
    try:
        if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
            raise HTTPException(status_code=500, detail="LiveKit credentials missing")

        channel_name = f"live_{current_user.id}_{int(time.time())}"
        grant = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
            .with_identity(channel_name)


        permissions = api.VideoGrants(
            room_join=True,
            room=channel_name,
            can_publish=True,
            can_publish_data=True,
            can_subscribe=True,
        )

        grant.with_grants(permissions)
        new_live = LiveStreamModel(
            host=current_user.to_ref(),
            channel_name=channel_name,
            livekit_token=grant.to_jwt(),
            is_premium=is_premium,
            entry_fee=entry_fee,
            status="live"
        )
        await new_live.insert()
        return {"livekit_token": grant.to_jwt()}


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/all/live",status_code=status.HTTP_200_OK)
async def get_all_livestream():
    return await LiveStreamModel.find_all().to_list()





