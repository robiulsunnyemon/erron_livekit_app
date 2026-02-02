import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.users.models.moderator_models import ModeratorModel
from typing import Union

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Union[UserModel, ModeratorModel]:
    return await verify_token(token)

async def verify_token(token: str) -> Union[UserModel, ModeratorModel]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # First attempt to get from UserModel
    user = await UserModel.get(user_id, fetch_links=True)
    if not user:
        # Check ModeratorModel if not found in UserModel
        user = await ModeratorModel.get(user_id, fetch_links=True)

    if user is None:
        raise credentials_exception

    return user

async def get_ws_current_user(token: str = Query(None)) -> Union[UserModel, ModeratorModel]:
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing")
    return await verify_token(token)
