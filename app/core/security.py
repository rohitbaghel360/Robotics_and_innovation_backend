from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings

BCRYPT_MAX_PASSWORD_BYTES = 72


@dataclass
class TokenPayload:
    user_id: str
    email: str | None = None
    name: str | None = None


def create_access_token(
    user_id: str,
    *,
    email: str | None = None,
    name: str | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    claims: dict[str, Any] = {"sub": user_id, "exp": expire}
    if email:
        claims["email"] = email
    if name:
        claims["name"] = name
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token_payload(token: str) -> TokenPayload | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return TokenPayload(
        user_id=str(user_id),
        email=payload.get("email"),
        name=payload.get("name"),
    )

def decode_access_token(token: str) -> str | None:
    """Return user id from token, or None if invalid."""
    data = decode_token_payload(token)
    return data.user_id if data else None

def _password_bytes(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
        )
    return encoded


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            _password_bytes(plain_password),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False