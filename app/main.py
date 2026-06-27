from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.db.registry  # noqa: F401 — register all ORM models
from app.api.v1.router import api_v1_router
from app.config import settings
from app.db import close_db, create_tables, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings

    init_db(settings.DB.URL, echo=settings.DEBUG)
    await create_tables()
    yield
    await close_db()

def create_app() -> FastAPI:

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs" if not settings.ENVIRONMENT == "production" else None,
        redoc_url="/redoc" if not settings.ENVIRONMENT == "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    @app.get("/")
    async def root():
        return {
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }

    return app
app = create_app()
