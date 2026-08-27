"""
FastAPI dependency injection functions.
All route handlers that need the DB session or the current user import from here.
"""
from __future__ import annotations

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import decode_access_token
from database import AsyncSessionLocal
from models import User

# ─────────────────────────────────────────────────────────────────────────────
# Database session
# ─────────────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for a single request, then close it."""
    async with AsyncSessionLocal() as session:
        yield session


# ─────────────────────────────────────────────────────────────────────────────
# Current user
# ─────────────────────────────────────────────────────────────────────────────


async def _resolve_user(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: AsyncSession,
) -> Optional[User]:
    """Decode the JWT and return the corresponding User row, or None."""
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency: return the authenticated User or raise 401.
    Ensures users can only act on their own data.
    """
    user = await _resolve_user(credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Dependency: return the User if authenticated, else None (no error)."""
    return await _resolve_user(credentials, db)


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency: enforce that the caller is an admin.
    Returns the User if admin, otherwise raises 403.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user
