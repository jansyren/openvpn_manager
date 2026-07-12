# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenVPN Manager is a web-based management tool for OpenVPN servers, providing centralized control over configuration, certificates, clients, routes, and backups across local and remote servers.

## Commands

### Backend (Python 3.11+, uses `uv`)

```bash
cd backend
uv sync                                        # Install dependencies
uv run alembic upgrade head                    # Run database migrations
uv run uvicorn app.main:app --reload           # Start dev server (port 8000)
uv run pytest                                  # Run all tests
uv run pytest tests/test_auth.py              # Run a single test file
uv run pytest -k "test_login"                 # Run tests matching a name pattern
uv run ovpn-create-admin                       # CLI: Create admin user
```

### Frontend (Node.js / TypeScript)

```bash
cd frontend
npm install
npm run dev           # Vite dev server (port 5173, proxies /api to backend)
npm run build         # Type-check + production build
npm run test:unit     # Vitest unit tests
npm run test:e2e      # Playwright end-to-end tests
npm run lint          # ESLint with auto-fix
npm run type-check    # Vue TSC type checking
```

### Docker

```bash
docker compose up -d  # Start all services (PostgreSQL, backend, frontend)
```

## Architecture

### Three-Tier Structure

```
Frontend (Vue 3 + TypeScript, Vite, PrimeVue 4)
    ↓ /api/v1
Backend API (FastAPI, Python, async SQLAlchemy)
    ↓
SQLite/PostgreSQL  |  SSH Execution (asyncssh)  |  File I/O
```

### Backend (`/backend/app/`)

- **`main.py`** — App factory: CORS, security headers, request logging middleware, 12 routers under `/api/v1/`
- **`api/`** — 12 routers: `auth`, `servers`, `vpn_instances`, `routes`, `clients`, `certificates`, `pam`, `easyrsa`, `backup`, `deploy`, `system`, `users`
- **`services/`** — Business logic: `server_service`, `client_generator`, `config_parser`, `backup_service`, `easyrsa_service`, `pam_service`, `deploy_service`, `auth_service`, `route_manager`, `service_manager`, `openvpn_directives`
- **`services/remote/`** — `Executor` abstraction: `local_executor.py` and `remote_executor.py` (asyncssh). All commands use `shell=False` with argument lists against an `ALLOWED_BINARIES` whitelist to prevent injection.
- **`db/models/`** — 8 models: `User`, `Server`, `VpnInstance`, `Certificate`, `VpnClient`, `Route`, `Backup`, `AuditLog`
- **`core/`** — `security.py` (JWT RS256, bcrypt, AES-256-GCM key encryption), `logging.py` (structlog + request UUID), `exceptions.py` (custom hierarchy)

### Frontend (`/frontend/src/`)

- **`api/`** — 12 Axios client modules; `client.ts` has JWT interceptors and auto-refresh on 401
- **`stores/`** — Pinia: `auth.ts` (session/token state), `servers.ts`
- **`router/index.ts`** — Auth guards (`requiresAuth`, `requiresSuperuser`)
- **`views/`** — Feature pages (servers, clients, certificates, backup, deploy, vpn, routes, pam, easyrsa, users)
- **`types/index.ts`** — All shared TypeScript interfaces

### Authentication Flow

1. Login → access token (response body) + refresh token (httpOnly cookie)
2. Axios adds `Authorization: Bearer <token>`; on 401, auto-calls `/auth/refresh`
3. RS256 asymmetric JWT: 15 min access tokens, 7-day refresh cookies
4. Account lockout after N failed attempts (configurable)

### Key Security Patterns

- SSH private keys encrypted at rest with AES-256-GCM + HKDF-derived keys
- Client `.ovpn` files stored encrypted, decrypted in memory only
- All remote commands executed via `shell=False` with `ALLOWED_BINARIES` whitelist
- Passwords passed via stdin pipes, never as CLI arguments
- SHA-256 hash verification for backup restore + path traversal protection
- `AuditLog` model records all mutations with `old_values`/`new_values` JSON

## Environment

Copy `.env.example` to `.env`. Key variables:
- `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` — RS256 PEM key paths
- `DATABASE_URL` — PostgreSQL (required for `alembic upgrade`; SQLite is used only by the test suite, which builds the schema via `create_all`, not migrations)
- `SSH_KEY_ENCRYPTION_SECRET` — AES-256-GCM encryption key
- `APP_SECRET_KEY` — ≥32 chars

## Database Migrations

Migrations live in `/backend/alembic/versions/`. After changing a model, generate and apply:
```bash
cd backend
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```
