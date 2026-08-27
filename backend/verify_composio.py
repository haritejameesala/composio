"""
verify_composio.py — read-only diagnostic + NO_AUTH flow verifier.

Place in:  D:\\composio\\backend\\
Run from:  D:\\composio\\backend\\   (same CWD uvicorn uses)

    python verify_composio.py            # config diagnosis + auth check (no writes)
    python verify_composio.py --full     # also runs the live NO_AUTH provisioning flow

This script does NOT modify the application. It imports the existing config
and service layer and reports on them. The API key is never printed in full.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import uuid
from pathlib import Path

# ── masking helpers ──────────────────────────────────────────────────────────


def mask(value: str) -> str:
    """first 4 + last 4 only; never the middle, never short keys."""
    if not value:
        return "<empty>"
    if len(value) <= 12:
        return f"<{len(value)} chars — too short to mask safely>"
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def fingerprint(value: str) -> str:
    """Stable non-reversible ID so you can compare two keys without revealing them."""
    if not value:
        return "-"
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def describe(label: str, value: str | None) -> None:
    if value is None:
        print(f"  {label:<28} <not set>")
        return
    print(f"  {label:<28} {mask(value)}   len={len(value)}  sha256[:12]={fingerprint(value)}")


PLACEHOLDERS = {
    "test_api_key_placeholder",
    "your_composio_api_key_here",
    "changeme",
    "placeholder",
}


# ── phase 1: where is the key coming from? ───────────────────────────────────


def phase_config() -> str:
    print("=" * 72)
    print("PHASE 1 — configuration source")
    print("=" * 72)

    cwd = Path.cwd()
    print(f"\n  Process CWD                  {cwd}")
    dotenv_path = cwd / ".env"
    print(f"  Resolved env_file            {dotenv_path}")
    print(f"  env_file exists              {dotenv_path.exists()}")
    if not dotenv_path.exists():
        print("\n  !! config.py uses env_file='.env', which resolves relative to the CWD.")
        print("     Run uvicorn from the backend/ directory, or Settings() will fail.")

    # raw value sitting in the .env file
    file_value: str | None = None
    if dotenv_path.exists():
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip().upper() == "COMPOSIO_API_KEY":
                file_value = v.strip().strip('"').strip("'")
                break

    shell_value = os.environ.get("COMPOSIO_API_KEY")

    print("\n  Candidate values:")
    describe("from backend/.env", file_value)
    describe("from shell environment", shell_value)

    # what the app actually loads
    sys.path.insert(0, str(cwd))
    from config import settings  # noqa: E402

    effective = settings.composio_api_key
    print()
    describe("EFFECTIVE (settings)", effective)

    # precedence verdict
    print("\n  Verdict:")
    if shell_value is not None and effective == shell_value and shell_value != file_value:
        print("    -> The SHELL environment variable is winning over backend/.env.")
        print("       pydantic-settings ranks OS env vars ABOVE the .env file.")
        print("       Unset it (PowerShell):")
        print("         Remove-Item Env:COMPOSIO_API_KEY")
        print("         [Environment]::SetEnvironmentVariable('COMPOSIO_API_KEY',$null,'User')")
    elif effective == file_value:
        print("    -> The value in backend/.env is what the app is using.")
    else:
        print("    -> Value came from neither file nor shell (check for an injected env var).")

    if effective.strip().lower() in PLACEHOLDERS or effective.lower().startswith("test_"):
        print("\n    !! This is a PLACEHOLDER, not a real Composio key.")
        print("       This is the cause of HTTP 401 APIKey_InvalidAPIKey.")

    # confirm nothing else reads it
    print("\n  Backend-only check:")
    print(f"    COMPOSIO_API_KEY in os.environ  {'COMPOSIO_API_KEY' in os.environ}")
    print("    (frontend must have zero references — verified separately by grep)")

    return effective


# ── phase 2: does the key authenticate? ──────────────────────────────────────


def phase_auth() -> bool:
    print("\n" + "=" * 72)
    print("PHASE 2 — does the key authenticate? (read-only API call)")
    print("=" * 72)

    from composio_service import _get_client  # noqa: E402
    from config import settings  # noqa: E402

    client = _get_client()
    try:
        resp = client.auth_configs.list(toolkit_slug=settings.default_toolkit_slug)
        print(f"\n  OK — authenticated. auth_configs for "
              f"'{settings.default_toolkit_slug}': {len(resp.items)}")
        for it in resp.items[:5]:
            print(f"    id={it.id}  scheme={getattr(it, 'auth_scheme', '?')} "
                  f"managed={getattr(it, 'is_composio_managed', '?')}")
        return True
    except Exception as exc:
        text = str(exc)
        print(f"\n  FAILED — {type(exc).__name__}")
        print(f"  {text[:400]}")
        if "401" in text or "InvalidAPIKey" in text:
            print("\n  -> The key reaching Composio is still not a valid key.")
            print("     Re-check PHASE 1 verdict above.")
        return False


# ── phase 3: native toolkit flow, end to end ─────────────────────────────────


async def phase_noauth() -> None:
    print("\n" + "=" * 72)
    print("PHASE 3 — toolkit auth classification and execution eligibility")
    print("=" * 72)

    from composio_service import ComposioService, _get_client  # noqa: E402
    from config import settings  # noqa: E402

    toolkit = settings.default_toolkit_slug
    info = ComposioService.get_toolkit_auth_info(toolkit)
    print(f"\n  [3.1] toolkit metadata for {toolkit}")
    print(f"        connection_mode={info['connection_mode']}")
    print(f"        supported_auth_schemes={info['supported_auth_schemes']}")
    if info["connection_mode"] != "native_no_auth":
        print("        auth_config_created=false")
        print("        connected_account_created=false")
        print("        direct_execution_skipped=true")
        print("        reason=toolkit advertises required credentialed auth")
        return

    client = _get_client()
    account_check_user = f"verify-{uuid.uuid4()}"
    accounts = client.connected_accounts.list(user_ids=[account_check_user], toolkit_slugs=[toolkit])
    print(f"        connected_accounts_before={len(accounts.items)}")
    print("        auth_config_created=false")

    print(f"\n  [3.2] tools.list(toolkit_slug={toolkit}) — pick a tool slug")
    tools = client.tools.list(toolkit_slug=toolkit, limit=8)
    items = getattr(tools, "items", [])
    for tool in items:
        print(f"        {tool.slug}")
    if not items:
        raise RuntimeError(f"No tools returned for toolkit '{toolkit}'")

    slug = next((tool.slug for tool in items if tool.slug == "SERPAPI_SEARCH"), items[0].slug)
    print(f"\n  [3.3] execute_tool(slug={slug}, user_id={account_check_user})")
    result = ComposioService.execute_tool(
        tool_slug=slug,
        composio_user_id=account_check_user,
        arguments={"query": "Composio AI tools integration"},
    )
    ok = result.get("successful", result.get("successfull", result.get("success")))
    print(f"        successful={ok}")
    print(f"        result_keys={list(result)[:10]}")

    accounts_after = client.connected_accounts.list(user_ids=[account_check_user], toolkit_slugs=[toolkit])
    print(f"        connected_accounts_after={len(accounts_after.items)}")
    if accounts_after.items:
        raise RuntimeError("Native toolkit execution unexpectedly created a connected account")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--full", action="store_true", help="run the live NO_AUTH flow")
    args = p.parse_args()

    phase_config()
    if not phase_auth():
        print("\nStopping: fix the API key before running the NO_AUTH flow.")
        sys.exit(1)

    if args.full:
        import asyncio
        asyncio.run(phase_noauth())
    else:
        print("\n(Run with --full to exercise the NO_AUTH provisioning flow.)")


if __name__ == "__main__":
    main()
