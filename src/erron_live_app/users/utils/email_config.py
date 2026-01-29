import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pydantic import BaseModel, EmailStr

# 🔹 Pydantic v2 model
class SendOtpModel(BaseModel):
    email: EmailStr
    otp: str

    model_config = {"from_attributes": True}


async def send_otp(otp_user: SendOtpModel):
    """
    Send OTP to user's email asynchronously using SendGrid
    """
    message = Mail(
        from_email=os.getenv("SENDER_EMAIL"),
        to_emails=otp_user.email,
        subject='🔑 Your OTP Code',
        plain_text_content=f'Your OTP code is: {otp_user.otp}'
    )
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(f"📧 Email sent to {otp_user.email}. Status: {response.status_code}")
        if response.status_code >= 400:
            print(f"❌ SendGrid Error Response: {response.body}")
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        if hasattr(e, 'body'):
            print(f"❌ Error Body: {e.body}")

async def send_custom_email(email: str, subject: str, content: str):
    """
    Generic function to send custom emails
    """
    message = Mail(
        from_email=os.getenv("SENDER_EMAIL", "InstaLive@erroneous.biz"),
        to_emails=email,
        subject=subject,
        plain_text_content=content
    )
    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(f"📧 Custom email sent to {email}. Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending custom email: {str(e)}")