import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

# 🔹 Pydantic v2 model
class SendOtpModel(BaseModel):
    email: EmailStr
    otp: str

    model_config = {"from_attributes": True}


async def send_otp(otp_user: SendOtpModel):
    """
    Send OTP to user's email asynchronously using SendGrid
    """
    try:
        message = Mail(
            from_email=os.getenv("SENDER_EMAIL"),
            to_emails=otp_user.email,
            subject='🔑 Your OTP Code',
            plain_text_content=f'Your OTP code is: {otp_user.otp}'
        )
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        logger.error(f"Error sending email to {otp_user.email}: {e}")

async def send_custom_email(email: str, subject: str, content: str):
    """
    Generic function to send custom emails
    """
    try:
        message = Mail(
            from_email=os.getenv("SENDER_EMAIL", "InstaLive@InstaLiveeous.biz"),
            to_emails=email,
            subject=subject,
            plain_text_content=content
        )
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        sg.send(message)
    except Exception as e:
        logger.error(f"Error sending custom email to {email}: {e}")
