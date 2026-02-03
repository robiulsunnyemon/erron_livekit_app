from fastapi import FastAPI
from instalive_live_app.streaming.routers.streaming import router as stream_router
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from instalive_live_app.db import lifespan
from instalive_live_app.core.exceptions_handler.http_exception_handler import http_exception_handler
from instalive_live_app.core.exceptions_handler.global_exception_handler import global_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from instalive_live_app.users.routers.auth_routers import router as auth_router
from instalive_live_app.users.routers.user_routers import user_router
from instalive_live_app.users.routers.follow_routers import router as follower_router
from instalive_live_app.finance.routers.finance import router as finance_router
from instalive_live_app.streaming.routers.gifting import router as gifting_router
from instalive_live_app.streaming.routers.interactions import router as interactions_router
from instalive_live_app.chating.routers.chat_routers import router as chat_router
from instalive_live_app.chating.routers.call_routers import router as call_router
from instalive_live_app.admin.routers import router as admin_router
from instalive_live_app.finance.routers.payout import router as payout_router
from instalive_live_app.notifications.routers import router as notification_router
from instalive_live_app.finance.routers.stripe_routers import router as stripe_router
from instalive_live_app.users.routers.apology_routers import router as apology_router
# Load environment variables
import os
load_dotenv()
app = FastAPI(
    title="InstaLive API",
    description="Real-time Streaming Platform API",
    version="1.0.0",
    lifespan=lifespan
)

if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")



origins = [
    "https://instalive.app",
    "https://admin.instalive.app",
    "http://localhost:5173",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False, # Changed to False as per review P0-1
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)



app.include_router(auth_router,prefix="/api/v1")
app.include_router(user_router,prefix="/api/v1")
app.include_router(stream_router,prefix="/api/v1")
app.include_router(follower_router,prefix="/api/v1")
app.include_router(finance_router,prefix="/api/v1")
app.include_router(gifting_router,prefix="/api/v1")
app.include_router(interactions_router,prefix="/api/v1")
app.include_router(chat_router,prefix="/api/v1")
app.include_router(call_router,prefix="/api/v1")
app.include_router(admin_router,prefix="/api/v1")
app.include_router(payout_router,prefix="/api/v1")
app.include_router(notification_router,prefix="/api/v1")
app.include_router(stripe_router,prefix="/api/v1")
app.include_router(apology_router,prefix="/api/v1")
