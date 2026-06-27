import urllib.parse
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.core.email import generate_numeric_otp, send_otp_email
from app.core.security import create_access_token, get_password_hash, verify_password
from app.modules.auth.models import LocalCredential, User, UserOtp, generate_id
from app.modules.auth.schemas import (
    GoogleProfileInspectResponse,
    RegisterInitResponse,
    TokenResponse,
    UserResponse,
    VerifyRegisterOtp,
)
from app.modules.auth.service import AuthService

router = APIRouter(tags=["Authentication"])

OTP_EXPIRY_MINUTES = 5


async def _issue_otp(
    db: AsyncSession,
    email: str,
    purpose: str,
    purpose_text: str,
    background_tasks: BackgroundTasks,
    *,
    commit: bool = True,
) -> None:
    otp = generate_numeric_otp()
    expiry = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    await db.execute(delete(UserOtp).where(UserOtp.email == email, UserOtp.purpose == purpose))
    db.add(UserOtp(email=email, otp_code=otp, purpose=purpose, expires_at=expiry))
    if commit:
        await db.commit()
    background_tasks.add_task(send_otp_email, email=email, otp_code=otp, purpose_text=purpose_text)


# --- Pydantic Validation Schemas ---
class UserRegister(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOtpAndResetPassword(BaseModel):
    email: EmailStr
    otp_code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=72)

@router.get("/google/login")
def get_google_login_url():
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    }
    url_args = urllib.parse.urlencode(params)
    return {"url": f"{base_url}?{url_args}"}

@router.get("/google/inspect", response_model=GoogleProfileInspectResponse)
def inspect_google_profile(code: str = Query(...)):
    if not settings.DEBUG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return AuthService.inspect_google_profile(code=code)

@router.get("/google/callback")
async def google_callback(code: str = Query(...), db: AsyncSession = Depends(get_db)):
    token_response = await AuthService.handle_google_login(code=code, db=db)
    frontend_success_url = f"{settings.FRONTEND_URL.rstrip('/')}/login"

    return RedirectResponse(
        url=f"{frontend_success_url}?{urllib.parse.urlencode({'token': token_response.access_token})}",
        status_code=status.HTTP_302_FOUND,
    )

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterInitResponse)
async def register_user(
    data: UserRegister,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create account (unverified) and email a 6-digit OTP."""
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing and existing.is_verified:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    try:
        hashed = get_password_hash(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if existing:
        existing.name = data.name.strip()
        user_id = str(existing.id)
        await db.flush()

        cred_stmt = select(LocalCredential).where(LocalCredential.user_id == user_id)
        cred_res = await db.execute(cred_stmt)
        credentials = cred_res.scalars().first()
        if credentials:
            credentials.password_hash = hashed
        else:
            db.add(LocalCredential(user_id=user_id, password_hash=hashed))
            await db.flush()
    else:
        user_id = generate_id(16)
        db.add(
            User(
                id=user_id,
                email=data.email,
                name=data.name.strip(),
                is_verified=False,
            )
        )
        await db.flush()

        db.add(LocalCredential(user_id=user_id, password_hash=hashed))
        await db.flush()

    await _issue_otp(
        db,
        email=data.email,
        purpose="SIGNUP",
        purpose_text="Account Registration",
        background_tasks=background_tasks,
        commit=False,
    )
    await db.commit()

    return RegisterInitResponse(
        message="Verification code sent to your email. It expires in 5 minutes.",
        email=data.email,
    )


@router.post("/register/verify", response_model=TokenResponse)
async def verify_register_otp(data: VerifyRegisterOtp, db: AsyncSession = Depends(get_db)):
    """Verify signup OTP and return JWT."""
    stmt = select(UserOtp).where(
        UserOtp.email == data.email,
        UserOtp.otp_code == data.otp_code,
        UserOtp.purpose == "SIGNUP",
        UserOtp.expires_at > datetime.utcnow(),
    )
    res = await db.execute(stmt)
    valid_otp = res.scalars().first()
    if not valid_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
        )

    user_stmt = select(User).where(User.email == data.email)
    user_res = await db.execute(user_stmt)
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    user.is_verified = True
    await db.delete(valid_otp)
    await db.commit()

    token = create_access_token(str(user.id), email=user.email, name=user.name)
    return TokenResponse(access_token=token, email=user.email, name=user.name)


@router.post("/login", response_model=TokenResponse)
async def login_user(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Validates local credentials and issues an active app JWT access token."""
    # 1. Fetch user records
    stmt = select(User).where(User.email == data.email)
    user_res = await db.execute(stmt)
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please complete OTP verification.",
        )

    # 2. Fetch password hash profile
    cred_stmt = select(LocalCredential).where(LocalCredential.user_id == user.id)
    cred_res = await db.execute(cred_stmt)
    credentials = cred_res.scalars().first()
    if not credentials or not verify_password(data.password, credentials.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # 3. Create active session token
    token = create_access_token(str(user.id), email=user.email, name=user.name)
    return TokenResponse(access_token=token, email=user.email, name=user.name)

@router.post("/forgot-password")
async def request_password_reset_otp(
    data: ForgotPasswordRequest, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == data.email)
    res = await db.execute(stmt)
    user = res.scalars().first()
    
    if user:
        await _issue_otp(
            db,
            email=data.email,
            purpose="PASSWORD_RESET",
            purpose_text="Password Reset Request",
            background_tasks=background_tasks,
        )

    return {"message": "Verification code dispatched if the account context profile exists."}

@router.post("/reset-password-verify")
async def verify_otp_and_change_password(data: VerifyOtpAndResetPassword, db: AsyncSession = Depends(get_db)):
    """Validates the stored database OTP and updates the credentials row cleanly."""
    
    # Query database to find a matching valid OTP transaction code window
    stmt = select(UserOtp).where(
        UserOtp.email == data.email,
        UserOtp.otp_code == data.otp_code,
        UserOtp.purpose == "PASSWORD_RESET",
        UserOtp.expires_at > datetime.utcnow()
    )
    res = await db.execute(stmt)
    valid_otp = res.scalars().first()
    
    if not valid_otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP verification code.")
        
    user_stmt = select(User).where(User.email == data.email)
    user_res = await db.execute(user_stmt)
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    try:
        password_hash = get_password_hash(data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cred_stmt = select(LocalCredential).where(LocalCredential.user_id == user.id)
    cred_res = await db.execute(cred_stmt)
    credentials = cred_res.scalars().first()

    if credentials is None:
        # Google-only users have no local_credentials row yet — create one
        db.add(LocalCredential(user_id=user.id, password_hash=password_hash))
    else:
        credentials.password_hash = password_hash
    
    # Clean up and burn the utilized OTP record so it can't be reused
    await db.delete(valid_otp)
    await db.commit()
    
    return {"message": "Password updated successfully. You can now log in using your new credentials."}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        is_verified=user.is_verified,
    )


@router.post("/logout")
async def logout_user():
    """Stateless JWT logout — client should discard the token."""
    return {"message": "Logged out successfully."}