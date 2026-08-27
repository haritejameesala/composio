"""
Pydantic schemas for all request and response bodies.
These are separate from the ORM models to keep serialisation logic clean.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, SecretStr


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    """Safe user representation — never includes password hash."""
    id: str
    email: str
    username: str
    is_admin: bool
    composio_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Connections
# ─────────────────────────────────────────────────────────────────────────────


class ConnectionResponse(BaseModel):
    """Representation of either a connected account or native toolkit."""
    id: Optional[str] = None
    user_id: str
    toolkit_slug: str
    composio_connected_account_id: Optional[str] = None
    composio_auth_config_id: Optional[str] = None
    status: str
    connection_mode: str
    test_tool_slug: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    auth_type: str = "credentialed"

    model_config = {"from_attributes": True}


class ConnectionListResponse(BaseModel):
    connections: List[ConnectionResponse]
    total: int


class ToolkitAuthInfo(BaseModel):
    toolkit_slug: str
    connection_required: bool
    connection_mode: str
    auth_type: str
    supported_auth_schemes: List[str]
    required_credentials: List[str] = Field(default_factory=list)
    test_tool_slug: Optional[str] = None
    display_name: Optional[str] = None


class ProvisionRequest(BaseModel):
    """Body for POST /api/connections."""
    toolkit_slug: Optional[str] = Field(
        default=None,
        description="Toolkit slug to connect. Defaults to the server-configured default.",
    )
    credentials: Optional[dict[str, SecretStr]] = Field(
        default=None,
        description="Transient toolkit credentials; never persisted or returned.",
    )


class OAuthInitiationResponse(BaseModel):
    redirect_url: str
    connected_account_id: str
    status: str


class ToolExecuteRequest(BaseModel):
    tool_slug: str = Field(description="Composio tool slug, e.g. SERPAPI_SEARCH")
    arguments: dict = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Admin
# ─────────────────────────────────────────────────────────────────────────────


class AdminUserRow(BaseModel):
    """Row in the admin user list."""
    id: str
    email: str
    username: str
    is_admin: bool
    composio_user_id: str
    created_at: datetime
    connection_count: int

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    users: List[AdminUserRow]
    total: int


class AdminConnectionDetail(BaseModel):
    """
    Merges our DB record with live Composio data when available.
    If Composio is unreachable the live_status will be None.
    """
    id: str
    user_id: str
    toolkit_slug: str
    composio_connected_account_id: str
    composio_auth_config_id: str
    connection_mode: str = "connected_account"
    db_status: str
    live_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AdminUserConnectionsResponse(BaseModel):
    user: UserPublic
    connections: List[AdminConnectionDetail]
    toolkits: List[ToolkitAuthInfo] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Generic
# ─────────────────────────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
