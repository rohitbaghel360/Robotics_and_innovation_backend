from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.exceptions import UnauthorizedError
from app.config import Settings
from app.core.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Missing or invalid authorization header")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise UnauthorizedError("Invalid or expired token")
    return user_id
