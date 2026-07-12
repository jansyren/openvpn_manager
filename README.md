# OpenVPN Manager

A web-based management tool for OpenVPN servers. Manage configuration, certificates, clients, routes, and backups across local and remote servers through a unified UI.

## Features

- **Server management** — Add local or remote OpenVPN servers (SSH-based); read and write `/etc/openvpn` config files with full directive support and descriptions
- **VPN instances** — Manage multiple OpenVPN server processes per host; edit port, protocol, device, network settings
- **Client management** — Generate `.ovpn` client profiles with embedded certificates and TLS-auth key; import existing PAM users with pre-existing certificates
- **Certificate management** — Full Easy-RSA PKI integration; create, revoke, and inspect client certificates; supports separate Easy-RSA servers
- **PAM integration** — Create/delete system users on the VPN server via PAM; enforces `nologin` shell for VPN-only accounts
- **Active Directory / LDAP** — Authenticate VPN users against AD; sync group members as VPN clients; deploy a self-contained auth plugin to the OpenVPN server
- **Route management** — Configure routes between multiple `tun` devices
- **Backup & restore** — Archive `/etc/openvpn` and Easy-RSA PKI directories; SHA-256 confirmation required for restore; automatic pre-restore snapshot
- **Deployment** — Deploy and configure OpenVPN and Easy-RSA from scratch on Ubuntu systems
- **User management** — Role-based access control (`admin`, `operator`, `viewer`, `vpn_user`) with full CRUD; local and LDAP users
- **Audit logging** — All mutating operations are logged

## Architecture

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy (async), PostgreSQL (SQLite is used only for the in-memory test suite) |
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

> **Database note:** `alembic upgrade` requires **PostgreSQL**. Some migrations
> use `ALTER TABLE … ADD CONSTRAINT`, which SQLite does not support, so SQLite
> cannot be used as a development database via migrations. SQLite is used only by
> the test suite, which builds the schema directly with `Base.metadata.create_all`.

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
| `DATABASE_URL` | PostgreSQL (e.g. `postgresql+asyncpg://…`). Required for migrations; SQLite is test-only |
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
| `vpn_user` | Download their own `.ovpn` config only — no access to management UI |

---

## Active Directory / LDAP Authentication

OpenVPN Manager can authenticate VPN clients against Active Directory (or any LDAP-compatible directory). The flow involves three components:

1. **LDAP config** — stored in the database; bind credentials encrypted with AES-256-GCM
2. **Auth plugin** — a Python script deployed to `/etc/openvpn/scripts/ldap_auth.py` on the VPN server
3. **Per-instance config** — a JSON file at `/etc/openvpn/ldap-auth-{instance_id}.json` passed as `argv[1]` to the script at connect time

### Prerequisites

The `ldap3` Python library must be installed on the **VPN server** (not the manager host):

```bash
apt install python3-ldap3
# or
pip3 install ldap3
```

### Step 1 — Create an LDAP configuration

Navigate to **Active Directory** in the sidebar.

Click **Add Configuration** and fill in:

| Field | Example | Notes |
|-------|---------|-------|
| Name | `Corporate AD` | Label shown in the UI |
| Server URL | `ldap://dc.example.com:389` | Use `ldaps://` for port 636 |
| Backup Server URL | `ldap://dc2.example.com:389` | Tried if primary is unreachable |
| Bind DN | `CN=svc-vpn,OU=ServiceAccounts,DC=example,DC=com` | Service account with read access |
| Bind Password | `…` | Encrypted at rest with AES-256-GCM |
| User Search Base | `OU=Users,DC=example,DC=com` | DN under which users are searched |
| User Filter | `(objectClass=person)` | Narrows which objects count as users |
| Username Attribute | `sAMAccountName` | `uid` for OpenLDAP |
| Group Search Base | `OU=Groups,DC=example,DC=com` | Used to enumerate group members for sync |
| Group Member Attribute | `member` | Attribute on the group listing its members |
| Use STARTTLS | off | Upgrade a plain LDAP connection to TLS |
| Verify TLS cert | off | Enable for production with a valid CA cert |

Click **Test Connection** to verify the bind credentials before saving.

### Step 2 — Map AD groups to application roles

Still on the **Active Directory** page, expand the configuration and add group → role mappings.

Each mapping says "members of this AD group get this application role":

| Group DN | Role |
|----------|------|
| `CN=VPN-Admins,OU=Groups,DC=example,DC=com` | `admin` |
| `CN=VPN-Operators,OU=Groups,DC=example,DC=com` | `operator` |
| `CN=VPN-Users,OU=Groups,DC=example,DC=com` | `vpn_user` |

When a user from multiple mapped groups logs in they receive the highest-priority role (`admin > operator > viewer > vpn_user`). Users with no matching group receive `vpn_user` by default.

### Step 3 — Enable LDAP on the VPN instance

Open the VPN instance → **Settings** tab → **Active Directory / LDAP Authentication** section.

1. Tick **Enable LDAP authentication on this instance**
2. Select the LDAP configuration created in Step 1
3. Add one or more **VPN User Groups** — the AD groups whose members are allowed to connect:

```
CN=VPN-Users,OU=Groups,DC=example,DC=com
```

Multiple groups can be added; any member of any listed group is permitted.

### Step 4 — Sync users and issue certificates

Click **Sync Users from AD**. For each member found in the configured groups the manager will:

- Create a local `User` record (role from group mappings, `auth_source=ldap`)
- Create a `VpnClient` record for the VPN instance
- Issue a PKI certificate via Easy-RSA (if a CA passphrase is stored on the instance)

Sync can be re-run at any time; existing clients are skipped.

### Step 5 — Deploy the auth plugin

Click **Deploy Auth Plugin**. The manager:

1. Writes `/etc/openvpn/scripts/ldap_auth.py` to the VPN server
2. Writes `/etc/openvpn/ldap-auth-{instance_id}.json` containing bind credentials, group DNs, and enforcement flags (mode `600`, readable by root only)

The deploy result shows the two directives to add to the server config. Open the **Config Editor** tab and add them:

```
script-security 2
auth-user-pass-verify "/etc/openvpn/scripts/ldap_auth.py /etc/openvpn/ldap-auth-4.json" via-file
```

**Save Config** and restart the OpenVPN service from the **Service** tab.

> **Note:** OpenVPN only allows one `auth-user-pass-verify` directive. The LDAP script handles both password verification and CN=username enforcement (controlled by the `enforce_cn_username` toggle on the instance). Do not use the separate CN verify script alongside the LDAP plugin.

### Step 6 — VPN client download

`vpn_user` accounts can log in to the OpenVPN Manager UI and see only the **My VPN Config** page, where they can download their personal `.ovpn` file. No other management pages are accessible.

### How the auth plugin works at connect time

When a client connects OpenVPN calls the script via `via-file`:

```
auth-user-pass-verify "/etc/openvpn/scripts/ldap_auth.py /etc/openvpn/ldap-auth-4.json" via-file
```

`via-file` means OpenVPN writes `username\npassword\n` to a mode-600 temp file and appends its path as an extra argument, so the script receives:

- `argv[1]` — path to the JSON config (`ldap-auth-4.json`)
- `argv[2]` — path to the temp credentials file (created and deleted by OpenVPN)
- `$common_name` — certificate CN, always set as an environment variable

The script (`ldap_auth.py`):

1. Reads the JSON config from `argv[1]`
2. Reads username and password from the temp file at `argv[2]`, then zeros the password from memory immediately
3. If `enforce_cn_username` is `true`, rejects if cert CN ≠ username
4. Binds the service account and searches for the user by `username_attr`
5. Binds as the found user DN to verify the password
6. If `vpn_groups` is non-empty, checks that the user DN appears in the `member` attribute of at least one listed group
7. Logs result to syslog (`/var/log/auth.log`, facility `auth`, tag `openvpn-ldap-auth`)
8. Exits `0` (accept) or `1` (reject)

Using `via-file` instead of `via-env` means the password is never visible in `/proc/<pid>/environ`, which is readable by any process running as root.

If the primary LDAP server is unreachable, `server_url_backup` is tried automatically.

### Re-deploying after config changes

Any change to the LDAP config (new group, updated password, changed search base) requires clicking **Deploy Auth Plugin** again to regenerate the JSON file on the server. User sync does not happen automatically — run it manually whenever the AD group membership changes.

### User management — LDAP users

On the **Users** page, set **Auth Source** to `AD / LDAP` when creating a user manually. No password is required; the user authenticates against AD at login time. Select the LDAP configuration to associate with the account.

Alternatively, users are provisioned automatically (JIT) on first login if they authenticate successfully against any active LDAP configuration.

---

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
