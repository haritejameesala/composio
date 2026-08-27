"""
FastAPI application entry point.

Startup sequence:
  1. Create all DB tables.
  2. Bootstrap admin user (from env vars) if it does not exist yet.
  3. Register all routers.
  4. Configure CORS.
"""
from __future__ import annotations

import logging
import sys
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from auth import hash_password
from config import settings
from database import AsyncSessionLocal, create_tables
from models import User
from routers import auth as auth_router
from routers import connections as connections_router
from routers import tools as tools_router
from routers import admin as admin_router

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("passlib").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Composio Integration Platform",
    description="Platform for managing Composio connections per user.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow the configured frontend origins only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router.router)
app.include_router(connections_router.router)
app.include_router(tools_router.router)
app.include_router(admin_router.router)


# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────


@app.on_event("startup")
async def on_startup() -> None:
    """Run once when the server starts."""
    logger.info("Starting up — creating DB tables…")
    await create_tables()

    # Bootstrap admin user
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == settings.admin_username)
        )
        existing_admin = result.scalar_one_or_none()
        if not existing_admin:
            admin_id = str(uuid.uuid4())
            admin = User(
                id=admin_id,
                email=settings.admin_email,
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
                is_admin=True,
                composio_user_id=admin_id,
            )
            db.add(admin)
            await db.commit()
            logger.info("Bootstrapped admin user: username=%s", settings.admin_username)
        else:
            logger.info("Admin user already exists: username=%s", settings.admin_username)

    logger.info("Startup complete. Composio API key: [REDACTED]")
    logger.info("Default toolkit: %s", settings.default_toolkit_slug)


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}
