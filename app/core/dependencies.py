from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.exceptions import UnauthorizedError
from app.core.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> str | None:
    """Return authenticated user id, or None for guest requests (no 401)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return decode_access_token(credentials.credentials)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> str:
    """Require a valid bearer token; raises 401 when missing or invalid."""
    user_id = await get_current_user_optional(credentials)
    if user_id is None:
        raise UnauthorizedError("Missing or invalid authorization header")
    return user_id
