# from fastapi import APIRouter, Depends
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.core.database import get_db
#
# router = APIRouter(prefix="/your-module", tags=["your-module"])
#
# def get_your_service(session: AsyncSession = Depends(get_db)):
#     from app.modules.your_module.repository import YourRepository
#     from app.modules.your_module.service import YourService
#     return YourService(YourRepository(session))
