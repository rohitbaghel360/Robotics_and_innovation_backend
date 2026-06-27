from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.health.router import router as health_router
from app.modules.shop.router import router as shop_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router, prefix="/auth")
api_v1_router.include_router(shop_router, prefix="/shop")
