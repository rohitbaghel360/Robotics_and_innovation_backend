from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import engine

router = APIRouter(tags=["health"])


async def _ping_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health")
async def health_check(request: Request):
    """Liveness probe — API process is running."""
    db_ok = await _ping_database()
    return {
        "status": "healthy",
        "environment": request.app.state.settings.ENVIRONMENT,
        "database": "connected" if db_ok else "disconnected",
    }


@router.get("/ready")
async def readiness_check():
    """Readiness probe — API can serve traffic (DB reachable)."""
    if not await _ping_database():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "disconnected"},
        )
    return {"status": "ready", "database": "connected"}
