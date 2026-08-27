"""
Auth router — register, login, and "me" endpoints.
Passwords are hashed with bcrypt and NEVER stored or logged in plaintext.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import create_access_token, hash_password, verify_password
from deps import get_current_user, get_db
from models import User
from schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    """Create a new user account. Composio user ID is set to the new user's UUID."""
    # Check uniqueness
    email_exists = await db.execute(select(User).where(User.email == body.email))
    if email_exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    username_exists = await db.execute(select(User).where(User.username == body.username))
    if username_exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken.")

    # Build and persist the user.
    # composio_user_id = str(user.id) — stable 1-to-1 mapping, no extra state.
    import uuid
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        is_admin=False,
        composio_user_id=user_id,  # identical to id by design
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Registered user: id=%s username=%s", user.id, user.username)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Authenticate and return a JWT access token."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(subject=user.id, is_admin=user.is_admin)
    logger.info("User logged in: id=%s username=%s", user.id, user.username)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's public profile."""
    return current_user
