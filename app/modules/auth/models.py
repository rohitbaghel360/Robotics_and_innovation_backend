import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


def generate_id(length: int = 16) -> str:
    """Generate a hex ID that fits VARCHAR columns (users.id max 25, linked_accounts max 16)."""
    return uuid.uuid4().hex[:length]


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(25), primary_key=True, default=lambda: generate_id(16))
    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    linked_accounts = relationship("LinkedAccount", back_populates="user", cascade="all, delete-orphan")

class LinkedAccount(Base):
    __tablename__ = "linked_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="unique_user_provider"),
        Index("idx_provider_user", "provider", "provider_user_id", unique=True),
        {"schema": "ri_web_auth"},
    )

    id = Column(String(16), primary_key=True, default=lambda: generate_id(16))
    user_id = Column(String(16), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_user_id = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="linked_accounts")

class LocalCredential(Base):
    __tablename__ = "local_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", name="unique_user_id"),
        {"schema": "ri_web_auth"},
    )

    user_id = Column(String(25), ForeignKey("ri_web_auth.users.id", ondelete="CASCADE"), primary_key=True)
    password_hash = Column(String(255), nullable=False)
    password_version = Column(Integer, default=1, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)


class UserOtp(Base):
    __tablename__ = "user_otps"
    __table_args__ = (
        Index("idx_otp_lookup", "email", "otp_code", "purpose"),
        {"schema": "ri_web_auth"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False)
    otp_code = Column(String(6), nullable=False)
    purpose = Column(
        Enum("SIGNUP", "PASSWORD_RESET", name="otp_purpose"),
        nullable=False,
    )
    expires_at = Column(TIMESTAMP, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

