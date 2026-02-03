import os
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from instalive_live_app.users.models.user_models import UserModel
from instalive_live_app.streaming.models.streaming import LiveStreamModel, LiveViewerModel, LiveCommentModel, LiveLikeModel, \
    LiveRatingModel, LiveStreamReportModel, LiveStreamReportReviewModel
from instalive_live_app.finance.models.transaction import TransactionModel
from instalive_live_app.streaming.models.gifts import GiftLogModel
from instalive_live_app.chating.models.chat_model import ChatMessageModel
from instalive_live_app.users.models.kyc_models import KYCModel
from instalive_live_app.users.models.moderator_models import ModeratorModel
from instalive_live_app.admin.models import SystemConfigModel, SecurityAuditLogModel
from instalive_live_app.finance.models.payout import PayoutConfigModel, BeneficiaryModel, PayoutRequestModel
from instalive_live_app.users.models.apology_models import ApologyModel
from instalive_live_app.notifications.models import NotificationModel
from instalive_live_app.finance.models.stripe_models import ProcessedStripeEvent

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME")


MODELS = [
    UserModel,
    LiveStreamModel,
    LiveViewerModel,
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
    NotificationModel,
    ApologyModel,
    ProcessedStripeEvent
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(MONGODB_URL,uuidRepresentation="standard")
    await init_beanie(
        database=client[DATABASE_NAME],
        document_models=MODELS,
    )
    logger.info(f"Connected to MongoDB: {DATABASE_NAME}")

    # ----------------------------------------
    # try:
    #     await UserModel.get_settings().motor_collection.drop()
    #     print("🗑️ UserModel collection dropped successfully.")
    # except Exception as e:
    #     print(f"⚠️ Error dropping collection: {e}")
    # ----------------------------------------

    yield

    client.close()
    logger.info("MongoDB connection closed.")
