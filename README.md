# Composio Hub

A full-stack Composio integration platform that allows users to discover
and connect third-party toolkits from a web UI, while keeping Composio
credentials and connection management securely on the backend.

## Overview

Composio Hub provides a controlled layer between application users and
Composio.

The main flow is:

``` text
User
  │
  ▼
React Frontend
  │
  │ JWT-authenticated API request
  ▼
FastAPI Backend
  │
  │ Composio SDK + server-side COMPOSIO_API_KEY
  ▼
Composio API
  │
  ├── Auth Configs
  ├── Connected Accounts
  ├── Toolkits
  ├── Users
  └── Tool Execution
```

The application maintains its own users and maps each platform user to a
stable Composio user ID.

------------------------------------------------------------------------

## Key Features

-   User registration and login
-   JWT-based authentication
-   Stable platform-user → Composio-user mapping
-   Dynamic Composio toolkit discovery
-   Authentication-aware toolkit classification
-   Native `NO_AUTH` toolkit support
-   API-key based toolkit connections
-   OAuth2-ready connection handling
-   Secure server-side Composio API access
-   User-level connection isolation
-   Tool execution through the backend
-   Admin dashboard for inspecting users and connections
-   Local connection metadata and Composio IDs
-   Composio Dashboard cross-verification
-   Idempotent connection provisioning
-   SQLite for local development

------------------------------------------------------------------------

## Architecture

### Frontend

-   React 18
-   TypeScript
-   Vite
-   Tailwind CSS
-   React Router
-   Axios

The frontend is responsible for:

-   User interaction
-   Login/register screens
-   Toolkit selection
-   Connection UI
-   Displaying connection status
-   Sending authenticated requests to the backend

The frontend must never contain the application's `COMPOSIO_API_KEY`.

### Backend

-   Python 3.10+
-   FastAPI
-   SQLAlchemy Async
-   Pydantic v2
-   Pydantic Settings
-   JWT
-   bcrypt
-   python-jose
-   aiosqlite

The backend is responsible for:

-   Authentication and authorization
-   User identity mapping
-   Toolkit discovery
-   Authentication classification
-   Connection provisioning
-   Composio SDK calls
-   Tool execution
-   Admin authorization
-   Preventing cross-user access

### Composio

The backend uses the Composio Python SDK to communicate with Composio.

The Composio API key is kept exclusively on the backend.

------------------------------------------------------------------------

## Authentication Model

There are two different authentication layers.

### 1. Application → Composio

The backend authenticates with Composio using:

``` text
COMPOSIO_API_KEY
```

This is an application/server credential.

It must never be exposed to the browser.

### 2. Composio → Third-Party Toolkit

The selected toolkit can use different authentication schemes:

``` text
NO_AUTH
API_KEY
OAUTH2
BASIC
etc.
```

These are toolkit-level credentials and are independent of the
application's Composio API key.

------------------------------------------------------------------------

## User Identity Mapping

When a user registers, the application creates an internal UUID.

That ID is also used as the user's Composio user ID:

``` text
Platform User ID
       │
       └──────────────► Composio User ID
```

Example:

``` text
Internal User ID:
42890990-4c2a-44be-b643-627e98ac5eee

Composio User ID:
42890990-4c2a-44be-b643-627e98ac5eee
```

The backend derives this value from the authenticated user.

The frontend cannot choose or override the Composio user ID during tool
execution.

------------------------------------------------------------------------

## Toolkit Authentication Flows

The application does not assume that every toolkit works the same way.

It first obtains toolkit metadata from Composio and determines the
appropriate authentication flow.

### NO_AUTH

A native `NO_AUTH` toolkit requires no third-party credential.

Flow:

``` text
User selects toolkit
       ↓
Backend checks toolkit metadata
       ↓
NO_AUTH
       ↓
No API-key input
       ↓
No OAuth redirect
       ↓
Tool can execute through Composio
```

No third-party API key is required.

### API_KEY

An API-key toolkit requires a credential supplied by the user.

Flow:

``` text
User selects toolkit
       ↓
UI requests toolkit API key
       ↓
User enters key
       ↓
Frontend sends it to FastAPI
       ↓
FastAPI sends credential to Composio
       ↓
Composio creates/uses the connected account
       ↓
Connection becomes available for that user
```

The user's third-party API key must be treated as a secret.

It must not be:

-   Stored in SQLite
-   Stored in localStorage
-   Stored in sessionStorage
-   Logged
-   Returned in API responses
-   Committed to Git

### OAuth2

OAuth2 toolkits use an authorization/redirect flow rather than asking
the user to paste an API key.

Conceptually:

``` text
User
  ↓
Connect
  ↓
FastAPI
  ↓
Composio OAuth flow
  ↓
Third-party authorization
  ↓
Callback / connection completion
  ↓
Connected account
```

------------------------------------------------------------------------

## Connection Lifecycle

A connection belongs to a specific application user.

Conceptually:

``` text
Platform User
     │
     ▼
Composio User ID
     │
     ▼
Toolkit
     │
     ▼
Auth Config
     │
     ▼
Connected Account
     │
     ▼
Tool Execution
```

The backend keeps local metadata needed to associate the application's
user with the Composio connection.

Composio remains responsible for the actual third-party
connection/authentication layer.

------------------------------------------------------------------------

## Tool Execution

All tool execution goes through the backend.

``` text
React
  │
  │ tool_slug + arguments
  ▼
FastAPI
  │
  │ authenticated user
  ▼
Composio SDK
  │
  │ user_id = authenticated user's Composio ID
  ▼
Composio Tool
  │
  ▼
Result
  │
  ▼
FastAPI → React
```

The client does not provide the authoritative `composio_user_id`.

The backend derives it from the authenticated JWT/user record.

------------------------------------------------------------------------

## Security

### Composio API Key

Store only in:

``` text
backend/.env
```

Never:

``` text
frontend/.env
GitHub
source code
browser storage
API response
logs
```

### User Toolkit Credentials

Third-party API keys such as Tavily or Perplexity should be treated as
transient secrets.

They should be sent only to the backend over the authenticated API
request and then passed to Composio as required.

They should not be persisted by the application.

### Authorization

Regular users can access only their own connections.

Admin endpoints require:

``` text
is_admin = true
```

Unauthorized users receive:

``` text
403 Forbidden
```

------------------------------------------------------------------------

## Project Structure

``` text
composio/
│
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── composio_service.py
│   │
│   ├── routers/
│   │   ├── auth.py
│   │   ├── connections.py
│   │   ├── tools.py
│   │   └── admin.py
│   │
│   ├── verify_composio.py
│   ├── requirements.txt
│   ├── .env.example
│   └── db/
│       └── app.db
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── ConnectionsPage.tsx
│   │   │   └── AdminPage.tsx
│   │   │
│   │   ├── components/
│   │   │   └── ConnectionCard.tsx
│   │   │
│   │   ├── api/
│   │   │   └── client.ts
│   │   └── ...
│   │
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

------------------------------------------------------------------------

## Database

For local development the application uses SQLite:

``` text
backend/db/app.db
```

Typical database URL:

``` env
DATABASE_URL=sqlite+aiosqlite:///./db/app.db
```

The database stores application metadata such as:

-   Users
-   Local connection records
-   Auth configuration cache
-   Connection relationships

Third-party secrets should not be stored in the database.

------------------------------------------------------------------------

## Environment Configuration

Create:

``` text
backend/.env
```

using:

``` text
backend/.env.example
```

Example:

``` env
COMPOSIO_API_KEY=your_composio_server_api_key

SECRET_KEY=replace_with_a_long_random_secret

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=1440

DATABASE_URL=sqlite+aiosqlite:///./db/app.db

DEFAULT_TOOLKIT_SLUG=

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change_this_password
```

Do not commit the real `.env` file.

------------------------------------------------------------------------

## Installation

### Requirements

Install:

-   Python 3.10+
-   Node.js
-   npm
-   A Composio account/project
-   A valid Composio server API key

------------------------------------------------------------------------

## Backend Setup

Open PowerShell:

``` powershell
cd D:\composio\backend
```

Install dependencies:

``` powershell
pip install -r requirements.txt
```

Configure:

``` text
backend/.env
```

Then start FastAPI:

``` powershell
uvicorn main:app --reload --port 8000
```

Backend:

``` text
http://127.0.0.1:8000
```

Swagger:

``` text
http://127.0.0.1:8000/docs
```

------------------------------------------------------------------------

## Frontend Setup

Open another terminal:

``` powershell
cd D:\composio\frontend
```

Install dependencies:

``` powershell
npm install
```

Start Vite:

``` powershell
npm run dev
```

Frontend:

``` text
http://localhost:5173
```

------------------------------------------------------------------------

## Verification

### Configuration and Composio Authentication

From the backend directory:

``` powershell
cd D:\composio\backend
python verify_composio.py
```

This should verify that the backend is using the intended Composio API
key without printing the secret.

### Full Verification

``` powershell
python verify_composio.py --full
```

The full verification should cover the available authentication paths
supported by the current toolkit metadata.

Do not interpret a toolkit requiring `API_KEY` as a `NO_AUTH` toolkit.

------------------------------------------------------------------------

## Manual End-to-End Test

### 1. Register

Open:

``` text
http://localhost:5173/register
```

Create a user.

### 2. Check User Mapping

Open the Connections page.

Verify:

``` text
Internal User ID
Composio User ID
```

are correctly associated.

### 3. Test a Native NO_AUTH Toolkit

Select a toolkit identified by live Composio metadata as requiring no
third-party credential.

Expected behavior:

``` text
No API-key field
No OAuth redirect
Connection/tool execution succeeds according to toolkit support
```

### 4. Test an API_KEY Toolkit

Select an API-key toolkit such as a supported Tavily/Perplexity
integration.

The UI should request the user's toolkit API key.

Expected behavior:

``` text
User enters API key
        ↓
Backend receives credential
        ↓
Composio connection created
        ↓
Connected Account ID returned
        ↓
Status displayed
```

The actual secret must never appear in the UI after submission,
database, logs, or API response.

### 5. Test User Isolation

Create:

``` text
User A
User B
```

Connect a toolkit for User A.

Verify User B cannot:

-   See User A's connection
-   Use User A's connected account
-   Supply User A's Composio user ID

### 6. Test Admin

Login as an administrator.

Open:

``` text
/admin
```

The admin should be able to inspect:

-   Platform user ID
-   Composio user ID
-   Toolkit
-   Authentication scheme
-   Connected Account ID
-   Auth Config ID
-   Connection status

------------------------------------------------------------------------

## Composio Dashboard Verification

Log in to the Composio Dashboard using the same Composio project.

Relevant areas may include:

``` text
Users
Auth Configs
Connected Accounts
Toolkits
API Keys
```

Use the IDs generated by the application to cross-check the
corresponding Composio resources.

Important:

The application should report only what is actually returned by the live
Composio API/dashboard. Do not assume that every local database record
must appear as a separate dashboard object.

------------------------------------------------------------------------

## API Overview

The backend exposes routes for:

### Authentication

``` text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
```

### Connections

``` text
GET    /api/connections
GET    /api/connections/toolkits
POST   /api/connections
DELETE /api/connections/{id}
```

### Tools

``` text
POST /api/tools/execute
```

### Admin

``` text
GET /api/admin/users
GET /api/admin/users/{user_id}/connections
```

See the automatically generated FastAPI documentation for the exact
request and response schemas:

``` text
http://127.0.0.1:8000/docs
```

------------------------------------------------------------------------

## Important Credential Distinction

There are two completely different keys involved.

### Application Composio API Key

``` text
COMPOSIO_API_KEY
```

Used by:

``` text
FastAPI → Composio
```

This belongs to the application/project.

### User Toolkit API Key

Example:

``` text
Tavily API key
Perplexity API key
```

Used by:

``` text
Composio → Third-party toolkit
```

These must never be confused.

The application Composio key should never be displayed in the toolkit
API-key input.

------------------------------------------------------------------------

## Common Errors

### `401 APIKey_InvalidAPIKey`

The Composio server rejected the application's `COMPOSIO_API_KEY`.

Check:

``` text
backend/.env
```

Then restart FastAPI.

### `403 APIKey_InsufficientPermissions`

The Composio API key is valid but lacks the required permission, for
example write access to connected accounts.

Create/use a project API key with the permissions required by the
backend operations.

### `404 Auth_Config_NotFound`

The local application has an Auth Config ID that does not exist in the
current Composio project.

Do not use mock/stale IDs.

Refresh/recreate the Auth Config through the live Composio API.

### `Auth_Config_NoAuthApp`

The selected toolkit does not support a custom `NO_AUTH` configuration.

Do not force it into the NO_AUTH flow.

Use the authentication scheme advertised by live toolkit metadata.

### `ConnectedAccountNotFound`

A tool requiring a connected account was executed for a user who does
not have an active connection for that toolkit.

Connect the toolkit first.

------------------------------------------------------------------------

## Development Principles

1.  Keep `COMPOSIO_API_KEY` server-side.
2.  Never trust a client-provided Composio user ID.
3.  Derive identity from the authenticated application user.
4.  Use live Composio toolkit metadata instead of hard-coded
    assumptions.
5.  Separate `NO_AUTH`, `API_KEY`, and OAuth2 flows.
6.  Never persist third-party API secrets unnecessarily.
7.  Never log credentials.
8.  Enforce user ownership on connection APIs.
9.  Enforce admin RBAC on admin APIs.
10. Avoid mock Composio IDs in production code.
11. Make connection provisioning idempotent.
12. Use the Composio Dashboard only as a cross-check of live Composio
    resources.

------------------------------------------------------------------------

## Demo Flow

For a client/team demonstration:

``` text
1. Register a user
       ↓
2. Show Internal User ID
       ↓
3. Show Composio User ID
       ↓
4. Select a toolkit
       ↓
5. Connect/authenticate it
       ↓
6. Show Connected Account + status
       ↓
7. Execute a tool
       ↓
8. Login as Admin
       ↓
9. Show the user's Composio information
       ↓
10. Cross-check in Composio Dashboard
```

The main value of the implementation is that the application provides
its own user and admin experience while Composio handles the underlying
third-party integration/authentication layer.

------------------------------------------------------------------------

## Security Checklist Before Sharing the Repository

Before pushing to GitHub or sending the project:

``` text
[ ] Remove backend/.env
[ ] Remove real COMPOSIO_API_KEY
[ ] Remove real third-party API keys
[ ] Remove production passwords
[ ] Add .env to .gitignore
[ ] Add node_modules to .gitignore
[ ] Add __pycache__ to .gitignore
[ ] Add frontend/dist to .gitignore
[ ] Review logs for secrets
[ ] Review Git history for accidentally committed secrets
[ ] Provide .env.example
```

If a secret was ever committed to Git, rotate/revoke it even if the file
is later deleted.

------------------------------------------------------------------------

## Status

The project is designed as a complete end-to-end Composio integration
layer:

``` text
Application User
      ↓
Authentication
      ↓
Stable Composio User ID
      ↓
Toolkit Discovery
      ↓
Authentication Classification
      ↓
NO_AUTH / API_KEY / OAuth2
      ↓
Composio Connection
      ↓
Tool Execution
      ↓
Admin Inspection
      ↓
Composio Dashboard Verification
```

For local development, SQLite is used to keep setup simple. The database
can be replaced with PostgreSQL for a production deployment without
changing the overall integration architecture.
