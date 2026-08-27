# Composio Integration Platform

A production-ready web application demonstrating a complete, secure Composio integration built from scratch with FastAPI, React + TypeScript + Tailwind, and SQLite (SQLAlchemy Async).

---

## Architecture Overview

```
 USER                               ADMIN
  │                                   │
  ▼                                   ▼
Platform UI (React)           Admin Dashboard (React)
  │ (JWT Bearer Token)                │ (JWT Bearer with is_admin=True)
  ▼                                   ▼
FastAPI Backend ─────────────── Admin API Router
  │
  ├── 1. Stable User ID mapping (User UUID == Composio userID)
  ├── 2. Auth Config Cache (auth_configs.create() once per toolkit)
  ├── 3. NO_AUTH Provisioning (connected_accounts.create() per user)
  ├── 4. Tool Execution Boundary (tools.execute() with injected userID)
  │
  ▼ (COMPOSIO_API_KEY — Backend Only)
Composio Platform API / SDK
  │
  ▼
Third-Party Toolkits (e.g. SERPAPI, HACKERNEWS)
```

---

## Security & Design Guarantees

1. **COMPOSIO_API_KEY is backend-only**: The API key is loaded into FastAPI settings from the backend `.env` file. It is NEVER exposed to the frontend/browser, never serialised in API responses, and never logged.
2. **Stable User Mapping**: When a user registers on our platform, our internal user ID (UUIDv4) is assigned directly to `composio_user_id`. Every Composio API call for that user passes this stable identifier.
3. **Strict User Ownership**: All user endpoints filter queries by `current_user.id`. No user can view, provision, or delete connections belonging to another user.
4. **Tool Execution Isolation**: When executing tools via `/api/tools/execute`, the backend injects `current_user.composio_user_id` server-side from the verified JWT; the client cannot supply a different `user_id`.
5. **Admin RBAC**: Admin endpoints (`/api/admin/users`, `/api/admin/users/{id}/connections`) require `is_admin=True` on the JWT, returning `403 Forbidden` for standard users.
6. **NO_AUTH Scheme Architecture**:
   - `auth_configs.create(toolkit={"slug": toolkit}, auth_config={"type": "use_custom_auth", "auth_scheme": "NO_AUTH"})` is executed **once** per toolkit and cached in the `auth_config_cache` table.
   - `connected_accounts.create(auth_config={"id": auth_config_id}, connection={"user_id": composio_user_id})` is executed per user/toolkit, creating an instantly `ACTIVE` connection.
   - `tools.execute(tool_slug, user_id=composio_user_id, arguments=...)` runs tool calls at runtime.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Example / Default |
|---|---|---|
| `COMPOSIO_API_KEY` | Your Composio API Key from the dashboard | `comp_...` |
| `DEFAULT_TOOLKIT_SLUG` | Default NO_AUTH toolkit for provisioning | `serpapi` |
| `SECRET_KEY` | Secret key for JWT signing (HS256) | `32+ character random hex` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiration time in minutes | `1440` (24 hours) |
| `DATABASE_URL` | Async database connection string | `sqlite+aiosqlite:///./db/app.db` |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `ADMIN_USERNAME` | Default bootstrap admin username | `admin` |
| `ADMIN_EMAIL` | Default bootstrap admin email | `admin@example.com` |
| `ADMIN_PASSWORD` | Default bootstrap admin password | `Admin1234!` |

### Frontend (`frontend/.env`)

| Variable | Description | Example / Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend URL (Optional when using Vite proxy) | `http://localhost:8000` |

---

## Quickstart & Local Development

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 2. Backend Setup & Run
```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and paste your real COMPOSIO_API_KEY

# Start the FastAPI server
uvicorn main:app --reload --port 8000
```
Backend will be live at: `http://localhost:8000`  
Swagger API docs: `http://localhost:8000/docs`

### 3. Frontend Setup & Run
```bash
# In a separate terminal, navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```
Frontend will be live at: `http://localhost:5173`

---

## Manual Test Procedure

### Flow 1: User Experience (Add Composio Connection)
1. Open `http://localhost:5173/register` in your browser.
2. Register a new user (e.g. `alice`, `alice@example.com`, `Password123!`).
3. You will be automatically redirected to the **Connections** page (`/connections`).
4. Notice the **Stable User Mapping** card displaying your internal Platform User ID and identical Composio User ID.
5. In the **Add Composio Toolkit** box, select **SERPAPI (NO_AUTH)** and click **"Add Composio Connection"**.
6. The connection is provisioned with status **ACTIVE** and immediately displays in your connection cards.
7. Click **"Test SERPAPI Tool"** to verify backend runtime tool execution via `tools.execute()`.

### Flow 2: Admin Experience (Composio Inspector)
1. Sign out and log in with the administrator credentials:
   - **Username**: `admin`
   - **Password**: `Admin1234!` (or click *"Fill Admin Credentials"*)
2. Click **Admin Dashboard** in the top navigation bar (`/admin`).
3. Search or select any user (e.g. `alice`).
4. Inspect the user's details:
   - Platform User ID (Internal)
   - Composio User ID
   - Provisioned toolkits, auth config IDs, and connected account IDs
   - Database status vs. Live status synced from the Composio API
5. Click **"Open Composio Dashboard ↗"** to cross-reference with [dashboard.composio.dev](https://dashboard.composio.dev).

---

## External Credentials & Dashboard Configuration

1. **Composio Account**: Sign up at [app.composio.dev](https://app.composio.dev) / [dashboard.composio.dev](https://dashboard.composio.dev).
2. **Obtain API Key**: Go to **Settings** → **API Keys** and generate a new key.
3. **Configure Backend**: Paste the key into `backend/.env` as `COMPOSIO_API_KEY=...`.
4. **Composio Dashboard Visibility**:
   - The Composio Dashboard displays project metrics, connected accounts, and auth configs.
   - For NO_AUTH toolkits, Composio handles requests with `ACTIVE` status without requiring third-party credentials.
   - Our admin dashboard complements Composio by exposing the internal platform user ID mapping, local DB state, and quick live status synchronization.

