import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from erron_live_app.users.models.user_models import UserModel

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserModel:
    return await verify_token(token)

async def verify_token(token: str) -> UserModel:
    print(f"DEBUG: Verifying token: {token[:20]}...")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        print(f"DEBUG: Token decoded. user_id: {user_id}")

        if user_id is None:
            print("DEBUG: user_id is None")
            raise credentials_exception

    except JWTError as e:
        print(f"DEBUG: JWT Decode Error: {e}")
        raise credentials_exception

    user = await UserModel.get(user_id, fetch_links=True)

    if user is None:
        print(f"DEBUG: User not found in DB for id: {user_id}")
        raise credentials_exception

    print(f"DEBUG: User verified: {user.email}")
    return user

async def get_ws_current_user(token: str = Query(None)) -> UserModel:
    print(f"DEBUG: get_ws_current_user called with token: {token[:10] if token else 'None'}...")
    if token is None:
        print("DEBUG: WebSocket token is missing")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing")
    return await verify_token(token)