"""
Admin router — user list and per-user connection view.

All endpoints require is_admin=True (enforced by require_admin dependency).
Admins can see any user's internal ID, composio_user_id, and connections.
They cannot modify connections (read-only admin view).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from composio_service import ComposioService
from deps import get_db, require_admin
from models import AuthConfigCache, Connection, User
from schemas import (
    AdminConnectionDetail,
    AdminUserConnectionsResponse,
    AdminUserListResponse,
    AdminUserRow,
    ToolkitAuthInfo,
    UserPublic,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=AdminUserListResponse)
async def admin_list_users(
    search: Optional[str] = Query(default=None, description="Filter by username or email"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserListResponse:
    """
    List all platform users with their Composio user IDs and connection counts.
    Supports optional search filter and pagination.
    """
    # Build user query with optional search
    query = select(User)
    if search:
        like = f"%{search}%"
        query = query.where(
            (User.username.ilike(like)) | (User.email.ilike(like))
        )

    # Count total for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Fetch paginated users
    users_result = await db.execute(query.offset(offset).limit(limit))
    users = users_result.scalars().all()

    # Build rows with connection counts
    rows: list[AdminUserRow] = []
    for user in users:
        count_result = await db.execute(
            select(func.count()).select_from(Connection).where(Connection.user_id == user.id)
        )
        conn_count = count_result.scalar_one()
        rows.append(
            AdminUserRow(
                id=user.id,
                email=user.email,
                username=user.username,
                is_admin=user.is_admin,
                composio_user_id=user.composio_user_id,
                created_at=user.created_at,
                connection_count=conn_count,
            )
        )

    logger.info("Admin listed %d users (search=%r)", len(rows), search)
    return AdminUserListResponse(users=rows, total=total)


@router.get("/users/{user_id}/connections", response_model=AdminUserConnectionsResponse)
async def admin_get_user_connections(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserConnectionsResponse:
    """
    Return a user's full connection details including live Composio status.

    Merges our DB records with live data from the Composio API.
    If Composio is unreachable, live_status will be None.
    """
    # Resolve the target user
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Fetch local connection records
    conns_result = await db.execute(
        select(Connection).where(Connection.user_id == user.id)
    )
    connections = conns_result.scalars().all()

    # Build a lookup of live Composio statuses for this user
    live_accounts = ComposioService.list_user_connected_accounts(user.composio_user_id)
    live_status_map: dict[str, str] = {
        acct.id: acct.status for acct in live_accounts
    }
    logger.info(
        "Admin fetched %d live accounts for user_id=%s", len(live_accounts), user.id
    )

    details: list[AdminConnectionDetail] = []
    for conn in connections:
        # Load related auth config
        ac_result = await db.execute(
            select(AuthConfigCache).where(AuthConfigCache.id == conn.auth_config_cache_id)
        )
        ac = ac_result.scalar_one_or_none()
        composio_auth_config_id = ac.composio_auth_config_id if ac else ""

        live_status = live_status_map.get(conn.composio_connected_account_id)

        # If status changed, update our DB record
        if live_status and live_status != conn.status:
            conn.status = live_status
            await db.commit()

        details.append(
            AdminConnectionDetail(
                id=conn.id,
                user_id=conn.user_id,
                toolkit_slug=conn.toolkit_slug,
                composio_connected_account_id=conn.composio_connected_account_id,
                composio_auth_config_id=composio_auth_config_id,
                db_status=conn.status,
                live_status=live_status,
                created_at=conn.created_at,
                updated_at=conn.updated_at,
            )
        )

    return AdminUserConnectionsResponse(
        user=UserPublic.model_validate(user),
        connections=details,
        toolkits=[ToolkitAuthInfo(**item) for item in ComposioService.list_toolkits()],
    )
