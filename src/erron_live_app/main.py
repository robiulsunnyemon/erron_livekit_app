from fastapi import FastAPI,status
from erron_live_app.streaming.routers.streaming import router as stream_router
from fastapi.staticfiles import StaticFiles
import os
from fastapi.middleware.cors import CORSMiddleware
from erron_live_app.db import lifespan
from erron_live_app.core.exceptions_handler.http_exception_handler import http_exception_handler
from erron_live_app.core.exceptions_handler.global_exception_handler import global_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from erron_live_app.users.routers.auth_routers import router as auth_router
from erron_live_app.users.routers.user_routers import user_router
from erron_live_app.users.routers.follow_routers import router as follower_router
from erron_live_app.finance.routers.finance import router as finance_router
from erron_live_app.streaming.routers.gifting import router as gifting_router
from erron_live_app.streaming.routers.interactions import router as interactions_router



app = FastAPI(
    title="Erron Livekit API",
    description="FastAPI with Beanie and Motor",
    version="1.0.0",
    lifespan=lifespan
)

if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")



origins = [
    "http://localhost:5173",
    "http://localhost:8000",
    "https://eron.mtscorporate.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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
##app.include_router(follower_router,prefix="/api/v1")
app.include_router(finance_router,prefix="/api/v1")
app.include_router(gifting_router,prefix="/api/v1")
app.include_router(interactions_router,prefix="/api/v1")