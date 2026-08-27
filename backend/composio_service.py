"""
Composio service layer — the ONLY place in the codebase that touches composio_client.

Rules enforced here:
  - COMPOSIO_API_KEY is read from settings and passed to the client; it is NEVER logged.
  - All logging uses safe representations (IDs and slugs only).
  - All SDK calls are wrapped with structured error handling.
  - Auth configs are created once per toolkit and cached in the DB.

SDK version: composio-client==1.43.0
"""
from __future__ import annotations

import logging
from typing import Optional

from composio_client import Composio as ComposioClient
from composio_client.types.connected_account_list_response import Item as ConnectedAccountItem
from composio_client.types.connected_account_retrieve_response import ConnectedAccountRetrieveResponse
from composio_client.types.auth_config_list_response import Item as AuthConfigItem
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import AuthConfigCache, Connection

logger = logging.getLogger(__name__)


def _safe_exception_text(exc: Exception, secrets: tuple[str, ...] = ()) -> str:
    text = str(exc)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


class ToolkitNotFoundError(RuntimeError):
    """Raised when Composio cannot resolve a toolkit slug."""


def _get_client() -> ComposioClient:
    """
    Return a fresh composio_client.Composio instance authenticated with the API key.
    The key is read from settings; it is NEVER logged or included in exceptions.
    """
    return ComposioClient(api_key=settings.composio_api_key)


class ComposioService:
    """
    Stateless service class.  Pass a DB session to each method that needs persistence.
    All methods are async-friendly: blocking SDK calls are synchronous but fast (HTTP).
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Auth Config management
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_toolkit_auth_info(toolkit_slug: str) -> dict:
        """Return Composio's default auth mode and supported credential modes."""
        client = _get_client()
        try:
            toolkit = client.toolkits.retrieve(toolkit_slug)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                raise ToolkitNotFoundError(
                    f"Composio toolkit '{toolkit_slug}' was not found."
                ) from exc
            raise RuntimeError(
                f"Could not inspect Composio toolkit '{toolkit_slug}': {exc}"
            ) from exc

        data = toolkit.model_dump() if hasattr(toolkit, "model_dump") else vars(toolkit)
        auth_details = data.get("auth_config_details") or []
        supported_schemes = [
            str(item.get("mode"))
            for item in auth_details
            if item.get("mode")
        ]
        managed_schemes = data.get("composio_managed_auth_schemes") or []
        is_native = data.get("type") == "native"
        required_credentials = [
            field.get("name")
            for item in auth_details
            for field in (item.get("fields", {}).get("connected_account_initiation", {}).get("required", []) or [])
            if field.get("name")
        ]
        no_auth = any(scheme.upper() == "NO_AUTH" for scheme in supported_schemes)
        native_no_auth = is_native and no_auth and not required_credentials and not managed_schemes
        oauth2 = "OAUTH2" in {scheme.upper() for scheme in supported_schemes + list(managed_schemes)}
        auth_type = "native_no_auth" if native_no_auth else "oauth2" if oauth2 else "api_key" if required_credentials else "credentialed"
        connection_required = not native_no_auth
        return {
            "toolkit_slug": toolkit_slug,
            "connection_required": connection_required,
            "connection_mode": "connected_account" if connection_required else "native_no_auth",
            "auth_type": auth_type,
            "supported_auth_schemes": sorted(set(supported_schemes + list(managed_schemes))),
            "required_credentials": required_credentials,
            "display_name": data.get("name"),
        }

    @staticmethod
    def list_toolkits() -> list[dict]:
        """Discover valid native toolkit slugs from Composio."""
        response = _get_client().toolkits.list(type="native", limit=100)
        result = []
        for toolkit in response.items:
            data = toolkit.model_dump() if hasattr(toolkit, "model_dump") else vars(toolkit)
            slug = data.get("slug")
            auth_schemes = data.get("auth_schemes") or []
            managed_schemes = data.get("composio_managed_auth_schemes") or []
            is_native_no_auth = bool(data.get("no_auth"))
            is_oauth2 = "OAUTH2" in {str(scheme).upper() for scheme in auth_schemes + managed_schemes}
            is_api_key = "API_KEY" in {str(scheme).upper() for scheme in auth_schemes + managed_schemes}
            result.append({
                "toolkit_slug": slug,
                "connection_required": not bool(data.get("no_auth")),
                "connection_mode": "native_no_auth" if data.get("no_auth") else "connected_account",
                "auth_type": "native_no_auth" if is_native_no_auth else "oauth2" if is_oauth2 else "api_key" if is_api_key else "credentialed",
                "supported_auth_schemes": auth_schemes,
                "required_credentials": [],
                "test_tool_slug": None,
                "display_name": data.get("name"),
            })
        return result

    @staticmethod
    def get_test_tool_slug(toolkit_slug: str) -> Optional[str]:
        """Return a real tool belonging to a toolkit, preferring no-auth tools."""
        response = _get_client().tools.list(toolkit_slug=toolkit_slug, limit=100)
        items = list(response.items)
        def has_no_required_inputs(item: object) -> bool:
            data = item.model_dump() if hasattr(item, "model_dump") else vars(item)
            parameters = data.get("input_parameters") or {}
            return not parameters.get("required")

        selected = next(
            (item for item in items if getattr(item, "no_auth", False) and has_no_required_inputs(item)),
            None,
        )
        return selected.slug if selected else None

    @staticmethod
    async def get_or_create_auth_config(
        toolkit_slug: str,
        db: AsyncSession,
        auth_scheme: str = "NO_AUTH",
    ) -> AuthConfigCache:
        """
        Return a cached auth config DB record for *toolkit_slug*, creating one on
        Composio and in our DB if it does not exist yet.

        This is idempotent: safe to call on every connection-provision request.
        """
        # 1. Check DB cache first.
        result = await db.execute(
            select(AuthConfigCache).where(AuthConfigCache.toolkit_slug == toolkit_slug)
        )
        cached = result.scalar_one_or_none()
        if cached and cached.auth_scheme.upper() == auth_scheme.upper():
            client = _get_client()
            try:
                client.auth_configs.retrieve(cached.composio_auth_config_id)
            except Exception as exc:
                if getattr(exc, "status_code", None) != 404:
                    raise RuntimeError(
                        f"Could not validate Composio auth config for toolkit '{toolkit_slug}': {exc}"
                    ) from exc
                logger.warning(
                    "Removing stale auth_config cache: toolkit=%s composio_id=%s",
                    toolkit_slug,
                    cached.composio_auth_config_id,
                )
                await db.execute(
                    Connection.__table__.delete().where(
                        Connection.auth_config_cache_id == cached.id
                    )
                )
                await db.delete(cached)
                await db.commit()
                cached = None
            else:
                logger.info(
                    "auth_config cache hit: toolkit=%s composio_id=%s",
                    toolkit_slug,
                    cached.composio_auth_config_id,
                )
                return cached
        elif cached:
            await db.delete(cached)
            await db.commit()

        # 2. Not cached — check Composio first to avoid creating duplicates.
        client = _get_client()
        existing_id: Optional[str] = None

        try:
            list_resp = client.auth_configs.list(toolkit_slug=toolkit_slug)
            for item in list_resp.items:
                # Look for a custom auth config with our scheme that we own.
                ac = item
                if (
                    hasattr(ac, "auth_scheme")
                    and str(getattr(ac, "auth_scheme", "")).upper() == auth_scheme.upper()
                    and (auth_scheme.upper() == "OAUTH2" or not getattr(ac, "is_composio_managed", True))
                ):
                    existing_id = ac.id
                    logger.info(
                        "Found existing Composio auth config: toolkit=%s composio_id=%s",
                        toolkit_slug,
                        existing_id,
                    )
                    break
        except Exception as exc:
            # Non-fatal — we'll try to create a new one below.
            logger.warning("Could not list auth configs for toolkit=%s: %s", toolkit_slug, exc)

        if not existing_id:
            # 3. Create a new auth config on Composio.
            try:
                create_resp = client.auth_configs.create(
                    toolkit={"slug": toolkit_slug},
                    auth_config={
                        "type": "use_composio_managed_auth" if auth_scheme.upper() == "OAUTH2" else "use_custom_auth",
                        **({} if auth_scheme.upper() == "OAUTH2" else {"auth_scheme": auth_scheme}),
                        "name": f"platform-{toolkit_slug}-{auth_scheme.lower()}",
                    },
                )
                existing_id = create_resp.auth_config.id
                logger.info(
                    "Created Composio auth config: toolkit=%s composio_id=%s scheme=%s",
                    toolkit_slug,
                    existing_id,
                    auth_scheme,
                )
            except Exception as exc:
                logger.error(
                    "Failed to create auth config: toolkit=%s scheme=%s error=%s",
                    toolkit_slug,
                    auth_scheme,
                    exc,
                )
                raise RuntimeError(
                    f"Could not create Composio auth config for toolkit '{toolkit_slug}': {exc}"
                ) from exc

        # 4. Persist to DB cache.
        cache_entry = AuthConfigCache(
            toolkit_slug=toolkit_slug,
            composio_auth_config_id=existing_id,
            auth_scheme=auth_scheme,
        )
        db.add(cache_entry)
        await db.commit()
        await db.refresh(cache_entry)
        logger.info(
            "Cached auth config: toolkit=%s db_id=%s",
            toolkit_slug,
            cache_entry.id,
        )
        return cache_entry

    @staticmethod
    async def initiate_oauth_connection(
        composio_user_id: str,
        toolkit_slug: str,
        db: AsyncSession,
    ) -> dict:
        """Create a Composio-managed OAuth link and persist non-secret metadata."""
        existing_result = await db.execute(
            select(Connection).where(
                Connection.user_id == composio_user_id,
                Connection.toolkit_slug == toolkit_slug,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return {
                "redirect_url": "",
                "connected_account_id": existing.composio_connected_account_id,
                "status": existing.status,
            }
        auth_config = await ComposioService.get_or_create_auth_config(
            toolkit_slug=toolkit_slug,
            db=db,
            auth_scheme="OAUTH2",
        )
        try:
            response = _get_client().link.create(
                auth_config_id=auth_config.composio_auth_config_id,
                user_id=composio_user_id,
                callback_url=settings.oauth_callback_url,
            )
        except Exception as exc:
            raise RuntimeError(
                f"OAuth initiation failed for toolkit '{toolkit_slug}': {exc}"
            ) from exc

        connection = Connection(
            user_id=composio_user_id,
            auth_config_cache_id=auth_config.id,
            toolkit_slug=toolkit_slug,
            composio_connected_account_id=response.connected_account_id,
            status="INITIATED",
        )
        db.add(connection)
        await db.commit()
        return {
            "redirect_url": response.redirect_url,
            "connected_account_id": response.connected_account_id,
            "status": "INITIATED",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Connected Account management
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    async def provision_no_auth_connection(
        composio_user_id: str,
        toolkit_slug: str,
        db: AsyncSession,
    ) -> Connection:
        """
        Provision a NO_AUTH connected account on Composio for *composio_user_id*
        and persist a local Connection record.

        Steps:
          1. Get or create auth config (cached).
          2. Create connected account on Composio (status → ACTIVE for NO_AUTH).
          3. Persist Connection in our DB.
        """
        existing_result = await db.execute(
            select(Connection).where(
                Connection.user_id == composio_user_id,
                Connection.toolkit_slug == toolkit_slug,
            )
        )
        existing_connection = existing_result.scalar_one_or_none()
        if existing_connection and existing_connection.status.upper() == "ACTIVE":
            logger.info(
                "Connection already provisioned: user_id=%s toolkit=%s db_id=%s",
                composio_user_id,
                toolkit_slug,
                existing_connection.id,
            )
            return existing_connection

        # Step 1: ensure auth config exists.
        auth_config_entry = await ComposioService.get_or_create_auth_config(
            toolkit_slug=toolkit_slug,
            db=db,
            auth_scheme="NO_AUTH",
        )

        # Step 2: provision connected account on Composio.
        client = _get_client()
        try:
            create_resp = client.connected_accounts.create(
                auth_config={"id": auth_config_entry.composio_auth_config_id},
                connection={"user_id": composio_user_id},
            )
            composio_ca_id = create_resp.id
            status = create_resp.status
            logger.info(
                "Provisioned connected account: user_id=%s toolkit=%s composio_ca_id=%s status=%s",
                composio_user_id,
                toolkit_slug,
                composio_ca_id,
                status,
            )
        except Exception as exc:
            logger.error(
                "Failed to provision connected account: user_id=%s toolkit=%s error=%s",
                composio_user_id,
                toolkit_slug,
                exc,
            )
            raise RuntimeError(
                f"Composio connected account creation failed for toolkit '{toolkit_slug}': {exc}"
            ) from exc

        # Step 3: persist in our DB.
        connection = Connection(
            user_id=composio_user_id,  # our user.id == composio_user_id
            auth_config_cache_id=auth_config_entry.id,
            toolkit_slug=toolkit_slug,
            composio_connected_account_id=composio_ca_id,
            status=status,
        )
        db.add(connection)
        await db.commit()
        await db.refresh(connection)
        logger.info(
            "Saved connection: db_id=%s user_id=%s toolkit=%s",
            connection.id,
            composio_user_id,
            toolkit_slug,
        )
        return connection

    @staticmethod
    async def provision_credentialed_connection(
        composio_user_id: str,
        toolkit_slug: str,
        auth_scheme: str,
        credential_field: str,
        credential: str,
        db: AsyncSession,
    ) -> Connection:
        """Create a credentialed connected account without persisting the secret."""
        existing_result = await db.execute(
            select(Connection).where(
                Connection.user_id == composio_user_id,
                Connection.toolkit_slug == toolkit_slug,
            )
        )
        existing_connection = existing_result.scalar_one_or_none()
        if existing_connection and existing_connection.status.upper() == "ACTIVE":
            return existing_connection

        auth_config_entry = await ComposioService.get_or_create_auth_config(
            toolkit_slug=toolkit_slug,
            db=db,
            auth_scheme=auth_scheme,
        )
        try:
            response = _get_client().connected_accounts.create(
                auth_config={"id": auth_config_entry.composio_auth_config_id},
                connection={
                    "user_id": composio_user_id,
                    "data": {credential_field: credential},
                },
            )
        except Exception as exc:
            raise RuntimeError(
                f"Composio connected account creation failed for toolkit '{toolkit_slug}': "
                f"{_safe_exception_text(exc, (credential,))}"
            ) from exc

        connection = Connection(
            user_id=composio_user_id,
            auth_config_cache_id=auth_config_entry.id,
            toolkit_slug=toolkit_slug,
            composio_connected_account_id=response.id,
            status=response.status,
        )
        db.add(connection)
        await db.commit()
        await db.refresh(connection)
        return connection

    @staticmethod
    def get_live_connection_status(composio_ca_id: str) -> Optional[str]:
        """
        Fetch the live status of a connected account from Composio.
        Returns None if the API call fails (network error, etc.).
        """
        client = _get_client()
        try:
            resp: ConnectedAccountRetrieveResponse = client.connected_accounts.retrieve(composio_ca_id)
            return resp.status
        except Exception as exc:
            logger.warning(
                "Could not fetch live status for composio_ca_id=%s: %s",
                composio_ca_id,
                exc,
            )
            return None

    @staticmethod
    def list_user_connected_accounts(composio_user_id: str) -> list[ConnectedAccountItem]:
        """
        Return all connected accounts on Composio for *composio_user_id*.
        Returns an empty list on any API error.
        """
        client = _get_client()
        try:
            resp = client.connected_accounts.list(user_ids=[composio_user_id])
            logger.info(
                "Listed %d connected accounts for user_id=%s",
                len(resp.items),
                composio_user_id,
            )
            return resp.items
        except Exception as exc:
            logger.warning(
                "Could not list connected accounts for user_id=%s: %s",
                composio_user_id,
                exc,
            )
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Tool execution
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def execute_tool(
        tool_slug: str,
        composio_user_id: str,
        arguments: dict,
    ) -> dict:
        """
        Execute a Composio tool on behalf of *composio_user_id*.
        Returns the raw response dict from Composio.
        Raises RuntimeError on failure.
        """
        client = _get_client()
        logger.info(
            "Executing tool: slug=%s user_id=%s args_keys=%s",
            tool_slug,
            composio_user_id,
            list(arguments.keys()),
        )
        try:
            resp = client.tools.execute(
                tool_slug,
                user_id=composio_user_id,
                arguments=arguments,
            )
            # resp is a ToolExecuteResponse pydantic model — convert to dict
            return resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
        except Exception as exc:
            logger.error(
                "Tool execution failed: slug=%s user_id=%s error=%s",
                tool_slug,
                composio_user_id,
                exc,
            )
            raise RuntimeError(f"Tool execution failed for '{tool_slug}': {exc}") from exc


# Module-level singleton for convenience
composio_service = ComposioService()
