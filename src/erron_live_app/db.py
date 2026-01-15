import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.streaming.models.streaming import LiveStreamModel,LiveViewerModel,LiveCommentModel,LiveLikeModel, LiveRatingModel
from erron_live_app.finance.models.transaction import TransactionModel
from erron_live_app.streaming.models.gifts import GiftLogModel
from erron_live_app.chating.models.chat_model import ChatMessageModel

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")


MODELS = [
    UserModel,
    LiveStreamModel,
    LiveViewerModel,
    LiveCommentModel,
    LiveCommentModel,
    LiveLikeModel,
    LiveRatingModel,
    TransactionModel,
    GiftLogModel,
    ChatMessageModel
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(MONGODB_URL,uuidRepresentation="standard")
    await init_beanie(
        database=client[DATABASE_NAME],
        document_models=MODELS,
    )
    print(f"✅ Connected to MongoDB: {DATABASE_NAME}")

    # ----------------------------------------
    # try:
    #     await UserModel.get_settings().motor_collection.drop()
    #     print("🗑️ UserModel collection dropped successfully.")
    # except Exception as e:
    #     print(f"⚠️ Error dropping collection: {e}")
    # ----------------------------------------

    yield

    client.close()
    print("👋 MongoDB connection closed.")
