import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from erron_live_app.users.models.user_models import UserModel
from erron_live_app.streaming.models.streaming import LiveStreamModel, LiveViewerModel, LiveCommentModel, LiveLikeModel, \
    LiveRatingModel, LiveStreamReportModel, LiveStreamReportReviewModel
from erron_live_app.finance.models.transaction import TransactionModel
from erron_live_app.streaming.models.gifts import GiftLogModel
from erron_live_app.chating.models.chat_model import ChatMessageModel
from erron_live_app.users.models.kyc_models import KYCModel
from erron_live_app.users.models.moderator_models import ModeratorModel
from erron_live_app.admin.models import SystemConfigModel, SecurityAuditLogModel
from erron_live_app.finance.models.payout import PayoutConfigModel, BeneficiaryModel, PayoutRequestModel
from erron_live_app.notifications.models import NotificationModel

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
    ChatMessageModel,
    KYCModel,
    LiveStreamReportModel,
    LiveStreamReportReviewModel,
    ModeratorModel,
    SystemConfigModel,
    SecurityAuditLogModel,
    PayoutConfigModel,
    BeneficiaryModel,
    PayoutRequestModel,
    NotificationModel
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
