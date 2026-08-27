"""
Connections router — list and provision Composio connected accounts.

Security:
  - get_current_user ensures every request is authenticated.
  - User can only see/create their OWN connections (filtered by user.id).
  - COMPOSIO_API_KEY never leaves composio_service.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from composio_service import ComposioService, ToolkitNotFoundError
from config import settings
from deps import get_current_user, get_db
from models import Connection, User
from schemas import (
    ConnectionListResponse,
    ConnectionResponse,
    ProvisionRequest,
    ToolkitAuthInfo,
    OAuthInitiationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.get("/toolkits", response_model=list[ToolkitAuthInfo])
async def list_toolkits(
    _current_user: User = Depends(get_current_user),
) -> list[ToolkitAuthInfo]:
    """Discover currently valid Composio native toolkit slugs."""
    try:
        return [ToolkitAuthInfo(**item) for item in ComposioService.list_toolkits()]
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/toolkits/{toolkit_slug}/test-tool")
async def get_test_tool(toolkit_slug: str, _current_user: User = Depends(get_current_user)) -> dict:
    """Resolve one executable tool lazily for a discovered toolkit."""
    try:
        return {"test_tool_slug": ComposioService.get_test_tool_slug(toolkit_slug)}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _connection_to_schema(conn: Connection) -> ConnectionResponse:
    """Convert a Connection ORM model to a ConnectionResponse schema."""
    composio_auth_config_id = (
        conn.auth_config_cache_entry.composio_auth_config_id
        if conn.auth_config_cache_entry
        else ""
    )
    return ConnectionResponse(
        id=conn.id,
        user_id=conn.user_id,
        toolkit_slug=conn.toolkit_slug,
        composio_connected_account_id=conn.composio_connected_account_id,
        composio_auth_config_id=composio_auth_config_id,
        status=conn.status,
        connection_mode="connected_account",
        test_tool_slug=None,
        auth_type="oauth2" if conn.auth_config_cache_entry and conn.auth_config_cache_entry.auth_scheme.upper() == "OAUTH2" else "api_key",
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


@router.get("", response_model=ConnectionListResponse)
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionListResponse:
    """
    Return all Composio connections for the authenticated user.
    Fetches from our DB; optionally refreshes status from Composio on each item.
    """
    result = await db.execute(
        select(Connection).where(Connection.user_id == current_user.id)
    )
    connections = result.scalars().all()

    items: list[ConnectionResponse] = []
    for conn in connections:
        from models import AuthConfigCache
        ac_result = await db.execute(
            select(AuthConfigCache).where(AuthConfigCache.id == conn.auth_config_cache_id)
        )
        conn.auth_config_cache_entry = ac_result.scalar_one_or_none()

        live_status = ComposioService.get_live_connection_status(
            conn.composio_connected_account_id
        )
        if live_status and live_status != conn.status:
            conn.status = live_status
            await db.commit()

        item = _connection_to_schema(conn)
        item.test_tool_slug = ComposioService.get_test_tool_slug(conn.toolkit_slug)
        items.append(item)

    logger.info(
        "Listed %d connections for user_id=%s", len(items), current_user.id
    )
    return ConnectionListResponse(connections=items, total=len(items))


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def provision_connection(
    body: ProvisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionResponse:
    """
    Make a toolkit available for the authenticated user.

    Flow:
      1. Resolve toolkit slug (from body or server default).
    2. Classify the toolkit using live Composio metadata.
    3. Execute directly for native NO_AUTH, or provision a credentialed account.
    """
    toolkit_slug = (body.toolkit_slug or settings.default_toolkit_slug).lower().strip()

    logger.info(
        "Provisioning connection: user_id=%s toolkit=%s",
        current_user.id,
        toolkit_slug,
    )

    try:
        auth_info = ComposioService.get_toolkit_auth_info(toolkit_slug)
        if not auth_info["connection_required"]:
            return ConnectionResponse(
                user_id=current_user.id,
                toolkit_slug=toolkit_slug,
                status="AVAILABLE_WITHOUT_CONNECTION",
                connection_mode="native_no_auth",
                test_tool_slug=ComposioService.get_test_tool_slug(toolkit_slug),
                auth_type="native_no_auth",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        if auth_info["auth_type"] == "oauth2":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use the OAuth connect endpoint for this toolkit.",
            )
        api_key = body.credentials.get("api_key") if body.credentials else None
        if auth_info["auth_type"] == "api_key" and not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This toolkit requires an API key.",
            )
        if auth_info["auth_type"] != "api_key" and not api_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This toolkit requires a credential.")
        auth_scheme = next(
            (scheme for scheme in auth_info["supported_auth_schemes"] if scheme.upper() != "NO_AUTH"),
            "API_KEY",
        )
        connection = await ComposioService.provision_credentialed_connection(
            composio_user_id=current_user.composio_user_id,
            toolkit_slug=toolkit_slug,
            auth_scheme=auth_scheme,
            credential_field=auth_info["required_credentials"][0] if auth_info["required_credentials"] else "generic_api_key",
            credential=api_key.get_secret_value(),
            db=db,
        )
        from models import AuthConfigCache
        ac_result = await db.execute(
            select(AuthConfigCache).where(AuthConfigCache.id == connection.auth_config_cache_id)
        )
        connection.auth_config_cache_entry = ac_result.scalar_one_or_none()
        response = _connection_to_schema(connection)
        response.test_tool_slug = ComposioService.get_test_tool_slug(toolkit_slug)
        response.auth_type = auth_info["auth_type"]
        return response
    except RuntimeError as exc:
        if isinstance(exc, ToolkitNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/oauth", response_model=OAuthInitiationResponse)
async def initiate_oauth(
    body: ProvisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OAuthInitiationResponse:
    """Start a Composio-managed OAuth connection for the authenticated user."""
    toolkit_slug = (body.toolkit_slug or settings.default_toolkit_slug).lower().strip()
    try:
        auth_info = ComposioService.get_toolkit_auth_info(toolkit_slug)
        if auth_info["auth_type"] != "oauth2":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Toolkit '{toolkit_slug}' does not use OAuth2.",
            )
        result = await ComposioService.initiate_oauth_connection(
            current_user.composio_user_id,
            toolkit_slug,
            db,
        )
        return OAuthInitiationResponse(**result)
    except ToolkitNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Delete a connection record from our DB.
    The user can only delete their OWN connections.
    """
    result = await db.execute(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found or does not belong to you.",
        )
    await db.delete(connection)
    await db.commit()
    logger.info(
        "Deleted connection: db_id=%s user_id=%s", connection_id, current_user.id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
