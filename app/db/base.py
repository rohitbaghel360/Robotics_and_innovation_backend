from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Single source of truth for the database/schema name. Driven by config
# (DB__NAME env var) so it is never hardcoded in the ORM models.
DB_SCHEMA = settings.DB.NAME


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base for all module models."""
