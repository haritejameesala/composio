"""
SQLAlchemy ORM models.

Three tables:
  - users             — platform users; composio_user_id == str(id)
  - auth_config_cache — one record per toolkit, stores Composio auth config ID
  - connections       — one record per user × toolkit, stores connected account ID
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # The Composio user_id used for all Composio API calls for this user.
    # We set this to str(id) at creation so the mapping is always 1-to-1.
    composio_user_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    connections: Mapped[list[Connection]] = relationship(
        "Connection", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        # Never include hashed_password in repr
        return f"<User id={self.id!r} username={self.username!r} is_admin={self.is_admin}>"


class AuthConfigCache(Base):
    """
    Caches Composio auth config IDs per toolkit so we create them only once.
    Before calling auth_configs.create(), check this table first.
    """
    __tablename__ = "auth_config_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    toolkit_slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    composio_auth_config_id: Mapped[str] = mapped_column(String(128), nullable=False)
    auth_scheme: Mapped[str] = mapped_column(String(64), nullable=False, default="NO_AUTH")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationships
    connections: Mapped[list[Connection]] = relationship(
        "Connection", back_populates="auth_config_cache_entry"
    )

    def __repr__(self) -> str:
        return (
            f"<AuthConfigCache toolkit={self.toolkit_slug!r} "
            f"composio_id={self.composio_auth_config_id!r}>"
        )


class Connection(Base):
    """
    Records a provisioned Composio connected account for one user × toolkit pair.
    """
    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    auth_config_cache_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("auth_config_cache.id", ondelete="RESTRICT"), nullable=False
    )
    toolkit_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Composio identifiers — populated after successful provisioning
    composio_connected_account_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # Status mirrors what Composio returns: ACTIVE, FAILED, INITIALIZING, etc.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="INITIALIZING")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="connections")
    auth_config_cache_entry: Mapped[AuthConfigCache] = relationship(
        "AuthConfigCache", back_populates="connections"
    )

    def __repr__(self) -> str:
        return (
            f"<Connection id={self.id!r} user_id={self.user_id!r} "
            f"toolkit={self.toolkit_slug!r} status={self.status!r}>"
        )
