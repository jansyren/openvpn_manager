# OpenVPN Manager

A web-based management tool for OpenVPN servers. Manage configuration, certificates, clients, routes, and backups across local and remote servers through a unified UI.

## Features

- **Server management** — Add local or remote OpenVPN servers (SSH-based); read and write `/etc/openvpn` config files with full directive support and descriptions
- **VPN instances** — Manage multiple OpenVPN server processes per host; edit port, protocol, device, network settings
- **Client management** — Generate `.ovpn` client profiles with embedded certificates and TLS-auth key; import existing PAM users with pre-existing certificates
- **Certificate management** — Full Easy-RSA PKI integration; create, revoke, and inspect client certificates; supports separate Easy-RSA servers
- **PAM integration** — Create/delete system users on the VPN server via PAM; enforces `nologin` shell for VPN-only accounts
- **Route management** — Configure routes between multiple `tun` devices
- **Backup & restore** — Archive `/etc/openvpn` and Easy-RSA PKI directories; SHA-256 confirmation required for restore; automatic pre-restore snapshot
- **Deployment** — Deploy and configure OpenVPN and Easy-RSA from scratch on Ubuntu systems
- **User management** — Role-based access control (`admin`, `operator`, `viewer`) with full CRUD
- **Audit logging** — All mutating operations are logged

## Architecture

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), SQLite / PostgreSQL |
| Frontend | Vue 3, TypeScript, Vite, PrimeVue 4, Pinia, Axios |
| Remote execution | asyncssh — all commands run via SSH on remote servers |
| Auth | JWT RS256 — 15 min access tokens + 7-day httpOnly refresh cookie |
| SSH key storage | AES-256-GCM (HKDF-derived key, decrypted in memory only) |

## Security

- All shell commands run with `shell=False` against an `ALLOWED_BINARIES` whitelist — no command injection possible
- Passwords passed via stdin pipe, never as CLI arguments
- Pydantic v2 strict validation + regex patterns on all path/name fields
- Backup restore requires SHA-256 checksum confirmation + path-traversal protection on tar extraction
- Rate limiting and account lockout on login endpoint

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env — set SSH_KEY_ENCRYPTION_SECRET and adjust CORS_ALLOWED_ORIGINS

# Generate RS256 JWT keys
openssl genrsa -out private.pem 4096
openssl rsa -in private.pem -pubout -out public.pem

docker compose up -d
```

The UI is available at `http://localhost:8080`. The default admin account is created on first run (see `APP_ADMIN_PASSWORD` in `.env`).

## Development Setup

**Backend**

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

## Configuration

Key environment variables (see `.env.example` for the full list):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLite (`sqlite+aiosqlite:///./app.db`) or PostgreSQL |
| `JWT_PRIVATE_KEY_PATH` | Path to RS256 private key |
| `JWT_PUBLIC_KEY_PATH` | Path to RS256 public key |
| `SSH_KEY_ENCRYPTION_SECRET` | Secret used to encrypt stored SSH private keys |
| `BACKUP_STORAGE_PATH` | Directory where backup archives are stored |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of allowed origins |

## Role-Based Access

| Role | Capabilities |
|------|-------------|
| `admin` | Full access — servers, users, backup, deploy, all settings |
| `operator` | Client and certificate management; read server config |
| `viewer` | Read-only access to all resources |

## API

All endpoints are under `/api/v1/`. Interactive docs available at `http://localhost:8000/docs` when running in development mode.

## Tests

```bash
# Backend
cd backend && uv run pytest

# Frontend unit tests
cd frontend && npm run test:unit

# Frontend e2e tests
cd frontend && npm run test:e2e
```
