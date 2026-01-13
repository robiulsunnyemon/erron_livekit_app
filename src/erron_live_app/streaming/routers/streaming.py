import os
from dotenv import load_dotenv
from fastapi import APIRouter,status,HTTPException
from livekit import api
from erron_live_app.streaming.schemas.streaming import TokenRequest

load_dotenv()
router = APIRouter(prefix="/streaming",tags=["Stream"])


LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


@router.post("/get-token",status_code=status.HTTP_201_CREATED)
async def get_token(request: TokenRequest):
    try:
        grant = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
            .with_identity(request.participant_name)


        permissions = api.VideoGrants(
            room_join=True,
            room=request.room_name,
            can_publish=request.is_host,
            can_publish_data=True,
            can_subscribe=True,
        )

        grant.with_grants(permissions)
        return {"livekit_token": grant.to_jwt()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


