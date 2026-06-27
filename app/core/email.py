import random
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from app.config import settings

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=True
)

def generate_numeric_otp() -> str:
    """Generates a secure 6-digit verification code string."""
    return f"{random.randint(100000, 999999)}"

async def send_otp_email(email: EmailStr, otp_code: str, purpose_text: str):
    """Dispatches a structured 6-digit code via Hostinger SMTP."""
    
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 8px; border: 1px solid #eee;">
                <h2 style="color: #2b6cb0; text-align: center;">R&I Ecosystem Verification</h2>
                <p>Hello,</p>
                <p>Use the secure verification code below to complete your <strong>{purpose_text}</strong>. This code is valid for 5 minutes.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <span style="font-size: 32px; font-weight: bold; tracking-space: 4px; background: #edf2f7; padding: 10px 30px; border-radius: 4px; color: #2d3748; letter-spacing: 5px;">
                        {otp_code}
                    </span>
                </div>
                <p style="font-size: 12px; color: #718096; text-align: center;">If you didn't request this code, please ignore this message.</p>
            </div>
        </body>
    </html>
    """

    message = MessageSchema(
        subject=f"Verification Code: {otp_code}",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    await fm.send_message(message)