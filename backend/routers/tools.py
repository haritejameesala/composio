"""
Tools router — execute a Composio tool on behalf of the authenticated user.

Security:
  - get_current_user ensures authentication.
  - user_id passed to Composio is ALWAYS current_user.composio_user_id.
  - No user can execute a tool as another user.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from composio_service import ComposioService
from deps import get_current_user
from models import User
from schemas import ToolExecuteRequest, ToolExecuteResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    body: ToolExecuteRequest,
    current_user: User = Depends(get_current_user),
) -> ToolExecuteResponse:
    """
    Execute a Composio tool for the authenticated user.

    The caller supplies the tool_slug and arguments; the backend injects
    the user's composio_user_id — it is NEVER accepted from the request body.
    """
    logger.info(
        "Tool execute request: slug=%s user_id=%s",
        body.tool_slug,
        current_user.id,
    )
    try:
        result = ComposioService.execute_tool(
            tool_slug=body.tool_slug,
            composio_user_id=current_user.composio_user_id,
            arguments=body.arguments,
        )
        return ToolExecuteResponse(success=True, data=result)
    except RuntimeError as exc:
        logger.error(
            "Tool execution error: slug=%s user_id=%s error=%s",
            body.tool_slug,
            current_user.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
