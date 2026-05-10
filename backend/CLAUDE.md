## Backend Commands

```bash
uv sync                                        # Install dependencies
uv run alembic upgrade head                    # Run database migrations
uv run uvicorn app.main:app --reload           # Start dev server (port 8000)
uv run pytest                                  # Run all tests
uv run pytest tests/test_auth.py              # Run a single test file
uv run pytest -k "test_login"                 # Run tests matching a name pattern
uv run ovpn-create-admin                       # CLI: Create admin user
```

## Architecture

- **`main.py`** — App factory: CORS, security headers, request logging middleware, 12 routers under `/api/v1/`
- **`routers/`** — 12 routers: `auth`, `servers`, `vpn_instances`, `routes`, `clients`, `certificates`, `pam`, `easyrsa`, `backup`, `deploy`, `system`, `users`
- **`services/`** — Business logic: `server_service`, `client_generator`, `config_parser`, `backup_service`, `easyrsa_service`, `pam_service`, `deploy_service`, `auth_service`, `route_manager`, `service_manager`, `openvpn_directives`
- **`services/remote/`** — `Executor` abstraction: `local_executor.py` and `remote_executor.py` (asyncssh). All commands use `shell=False` with argument lists against an `ALLOWED_BINARIES` whitelist to prevent injection.
- **`db/models/`** — 8 models: `User`, `Server`, `VpnInstance`, `Certificate`, `VpnClient`, `Route`, `Backup`, `AuditLog`
- **`core/`** — `security.py` (JWT RS256, bcrypt, AES-256-GCM key encryption), `logging.py` (structlog + request UUID), `exceptions.py` (custom hierarchy)

## Database Migrations

Migrations live in `alembic/versions/`. After changing a model:

```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```
