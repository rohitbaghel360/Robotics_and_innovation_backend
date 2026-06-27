import logging

import requests
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import create_access_token
from app.modules.auth.models import LinkedAccount, User, generate_id
from app.modules.auth.schemas import GoogleProfileInspectResponse, TokenResponse

logger = logging.getLogger(__name__)

GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_PROFILE_KEYS = (
    "sub",
    "email",
    "email_verified",
    "name",
    "given_name",
    "family_name",
    "picture",
    "locale",
    "hd",
)


class AuthService:

    @staticmethod
    def _pick_profile_fields(payload: dict) -> dict:
        return {key: payload.get(key) for key in GOOGLE_PROFILE_KEYS if key in payload}

    @staticmethod
    def _extract_display_name(user_info: dict) -> str | None:
        name = user_info.get("name")
        if name and str(name).strip():
            return str(name).strip()

        given = user_info.get("given_name")
        family = user_info.get("family_name")
        parts = [str(part).strip() for part in (given, family) if part and str(part).strip()]
        if parts:
            return " ".join(parts)

        if given and str(given).strip():
            return str(given).strip()

        return None

    @staticmethod
    def _fetch_google_userinfo(access_token: str) -> dict | None:
        response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if not response.ok:
            logger.warning("Google userinfo request failed: %s %s", response.status_code, response.text)
            return None
        return response.json()

    @staticmethod
    def _sync_user_name(user: User, name: str | None) -> None:
        if name and user.name != name:
            user.name = name

    @staticmethod
    def _build_token_response(user: User, access_token: str) -> TokenResponse:
        return TokenResponse(
            access_token=access_token,
            name=user.name,
            email=user.email,
        )

    @classmethod
    def verify_google_code_and_get_user_info(cls, code: str) -> dict:
        """Exchange code for tokens, verify ID token, and merge OpenID userinfo profile."""
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        response = requests.post(token_url, data=data)
        if not response.ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code with Google.",
            )

        tokens = response.json()
        id_token_jwt = tokens.get("id_token")
        if not id_token_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token response did not include an id_token.",
            )

        try:
            id_info = id_token.verify_oauth2_token(
                id_token_jwt,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token payload.",
            ) from exc

        access_token = tokens.get("access_token")
        if access_token:
            userinfo = cls._fetch_google_userinfo(access_token)
            if userinfo:
                id_info = {**id_info, **userinfo}

        if settings.DEBUG:
            logger.info(
                "Google profile fields: id_token=%s userinfo_merged=%s extracted_name=%s",
                cls._pick_profile_fields(dict(id_info)),
                bool(access_token),
                cls._extract_display_name(id_info),
            )

        return id_info

    @classmethod
    def inspect_google_profile(cls, code: str) -> GoogleProfileInspectResponse:
        """Return Google profile fields for debugging (does not create a user)."""
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        response = requests.post(token_url, data=data)
        if not response.ok:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange authorization code with Google.",
            )

        tokens = response.json()
        id_token_jwt = tokens.get("id_token")
        if not id_token_jwt:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token response did not include an id_token.",
            )

        try:
            id_info = id_token.verify_oauth2_token(
                id_token_jwt,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token payload.",
            ) from exc

        userinfo_fields = None
        access_token = tokens.get("access_token")
        if access_token:
            userinfo_fields = cls._fetch_google_userinfo(access_token)

        merged = {**id_info, **(userinfo_fields or {})}
        return GoogleProfileInspectResponse(
            extracted_name=cls._extract_display_name(merged),
            id_token_fields=cls._pick_profile_fields(dict(id_info)),
            userinfo_fields=cls._pick_profile_fields(userinfo_fields) if userinfo_fields else None,
        )

    @classmethod
    async def handle_google_login(cls, code: str, db: AsyncSession) -> TokenResponse:
        """Processes user validation and handles database tracking entries."""
        user_info = cls.verify_google_code_and_get_user_info(code)

        email = user_info.get("email")
        name = cls._extract_display_name(user_info)
        provider_user_id = user_info.get("sub")  # Google's unique persistent user ID
        is_email_verified = user_info.get("email_verified", False)

        if not email or not provider_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incomplete profile payload returned from Google provider.",
            )

        # 1. Check if the linked account already exists
        linked_result = await db.execute(
            select(LinkedAccount).where(
                LinkedAccount.provider == "google",
                LinkedAccount.provider_user_id == provider_user_id,
            )
        )
        linked_account = linked_result.scalar_one_or_none()

        if linked_account:
            user_result = await db.execute(
                select(User).where(User.id == linked_account.user_id)
            )
            user = user_result.scalar_one_or_none()
            cls._sync_user_name(user, name)
            await db.commit()
            access_token = create_access_token(
                user.id, email=user.email, name=user.name
            )
            return cls._build_token_response(user, access_token)

        # 2. Check if a user with this email already exists (maybe created via passwords previously)
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()

        if not user:
            user = User(
                id=generate_id(16),
                email=email,
                name=name,
                is_verified=is_email_verified,
            )
            db.add(user)
            await db.flush()
        else:
            cls._sync_user_name(user, name)

        new_link = LinkedAccount(
            id=generate_id(16),
            user_id=user.id,
            provider="google",
            provider_user_id=provider_user_id,
        )
        db.add(new_link)
        await db.commit()

        access_token = create_access_token(
            user.id, email=user.email, name=user.name
        )
        return cls._build_token_response(user, access_token)