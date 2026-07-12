# OpenVPN Manager — Functional & Technical Specification

_This specification describes the system as it is intended to behave, reconstructed from the implementation at the `main` branch. It is the reference for what the software does; deviations found during review are cross-referenced to [IMPROVEMENTS.md](./IMPROVEMENTS.md) with tags like (B4), (F16)._

## 1. Purpose & scope

OpenVPN Manager provides a web UI and REST API to centrally administer OpenVPN deployments across local and remote (SSH) hosts. It manages: servers, VPN instances (individual OpenVPN server processes/configs), routes, client profiles and their certificates, an Easy-RSA PKI, PAM users, LDAP/Active Directory integration, backup/restore, and application users with role-based access.

## 2. Actors & roles

Application roles, highest to lowest privilege (`ROLE_PRIORITY` in `ldap_service.py`):

| Role | Intended capability |
|------|--------------------|
| `admin` | Full control of all resources, users, servers, PKI, deploy, LDAP config. |
| `operator` | Day-to-day operations: manage VPN clients/certs/routes; view the user list and generate certificates for `vpn_user` accounts; delete only `vpn_user` accounts. Cannot create users or change roles. |
| `viewer` | Read-oriented access to operational resources. |
| `vpn_user` | Self-service only: view/download their own VPN profile at `/my-vpn`. Restricted to that route when it is their only role. |

There is also a boolean `is_superuser` flag, reserved for local "break-glass" accounts (created via CLI or the first-run bootstrap). Authorization is satisfied by **`is_superuser` OR the appropriate active role**, so LDAP-provisioned admins (who are never `is_superuser`) still pass admin checks via their role.

### Multi-role & role switching
A user may hold several roles simultaneously, stored one-row-per-role in `user_roles`, each tagged `source = ldap | manual`:
- **LDAP-sourced roles** are recomputed from the user's AD group membership on *every* login (fresh `memberOf` fetch → mapped through `ldap_group_role_mappings`).
- **Manual roles** are assigned by an admin via the Users page and are preserved across LDAP recomputes (only `ldap`-sourced rows are replaced on login).
- The access token carries an `active_role`; a multi-role user switches it via `POST /auth/switch-role`, which reissues tokens (the refresh token also carries `active_role` so a silent refresh does not revert the switch).

## 3. Authentication

1. `POST /api/v1/auth/login` with username/password. Local users authenticate against the bcrypt hash; unknown users are JIT-provisioned against any active LDAP config; existing LDAP users are re-validated against the directory and have their roles recomputed.
2. On success: an access token (RS256, ~15 min) in the response body + a refresh token (7-day, httpOnly, `SameSite=Strict`, path `/api/v1/auth`) in a cookie.
3. The SPA holds the access token in memory only and sends it as `Authorization: Bearer`. On a 401 it silently calls `POST /auth/refresh` (cookie-based) once and retries.
4. `POST /auth/logout` blacklists the access token's JTI and clears the cookie. _(Known gap: the refresh token JTI is not blacklisted — B8.)_
5. Account lockout: after N failed attempts a username is locked for a configured duration. _(Implemented as in-memory state — B6; per-IP/global rate limiting is configured but **not implemented** — B5.)_

## 4. Functional modules

### 4.1 Servers
CRUD for managed hosts (`local` or remote SSH). Remote servers store an AES-GCM-encrypted SSH private key and optional sudo password; SSH host-key fingerprint is captured (TOFU). Create/edit/delete are admin-only.

### 4.2 VPN instances
Each instance represents one OpenVPN server process on a host: protocol/port/device, network, config path, PKI directory, Easy-RSA binding, PAM/LDAP auth toggles, TLS-auth key, and an encrypted CA passphrase. Supports config discovery on the host, reading/writing the OpenVPN config via a structured directive model (`openvpn_directives.py` + `config_parser.py`), service control (start/stop/restart/status), and log tailing.

### 4.3 Clients & certificates
A VPN client is a named profile bound to an instance (`client_type` = `user` or `site`). Creating a client can issue a fresh certificate via Easy-RSA, import an existing one, and (for user clients) generate a downloadable `.ovpn`. Certificates track serial/validity/revocation; revocation and renewal are superuser-only. `vpn_user`-role callers may only see and download **their own** client (matched by username).

### 4.4 Routes
Managed push/iroute entries per server/instance, applied to the running configuration.

### 4.5 PAM users
Manage system PAM accounts used for OpenVPN `auth-user-pass` authentication, including certificate generation for those users. Admin-only.

### 4.6 LDAP / Active Directory
- Multiple LDAP configs (server URL, bind DN + encrypted password, search bases, filters, TLS settings).
- `ldap_group_role_mappings` map an AD group DN → an application role. A user's roles are the union of all matching groups.
- `vpn_instance_ldap_groups` bind AD groups to a VPN instance for the sync flow.
- **Sync**: `POST /ldap/vpn-instances/{id}/sync` gathers members across the instance's configured groups (accumulating each member's full set of matching groups), JIT-creates users + VPN clients, and issues certificates where PKI is configured.
- **Deploy**: generates the OpenVPN LDAP-auth plugin script/config for an instance.
- TLS certificate verification for LDAP defaults to **off** (B12) — configurable per config.

### 4.7 Backup & restore
Create/download/restore/delete backup archives of server configuration and PKI. Restore verifies a SHA-256 hash and guards against tar path traversal. Create/restore/delete are superuser-only; list/download are available to any authenticated user. _(Frontend does not currently gate the mutating buttons — F17.)_

### 4.8 Users (application accounts)
Admins manage application users (local or LDAP-manual). Operators may list users and act on `vpn_user` accounts (generate certs, delete) but cannot create users or change roles. Editing an LDAP user's role sets a `manual` role that survives login recomputes.

### 4.9 System
Read/purge the `AuditLog`. _(The audit log is defined but **never written** by any code path — B9; the read/purge endpoints operate on an always-empty table.)_

## 5. API surface

All endpoints are under `/api/v1/`. Routers: `auth`, `servers`, `vpn_instances`, `routes`, `clients`, `certificates`, `pam`, `easyrsa`, `backup`, `deploy`, `system`, `users`, `ldap`. Authorization is enforced by FastAPI dependencies:
- `get_current_user` — any valid token.
- `get_current_operator` — `is_superuser` OR active role in {admin, operator}.
- `get_current_superuser` — `is_superuser` OR active role == admin.
- `get_active_role` — exposes the token's active role for finer checks (e.g. the `vpn_user` own-client filter).

## 6. Data model (persistent entities)

`User`, `UserRole` (user_id, role, source; unique per triple), `Server`, `VpnInstance`, `VpnClient`, `Certificate`, `Route`, `Backup`, `AuditLog`, `PamUser`, `PamGroup`, `LdapConfig`, `LdapGroupRoleMapping`, `VpnInstanceLdapGroup`.

Notable conventions/constraints:
- `User.role` is the "primary" (highest-priority) role, a denormalized convenience alongside `user_roles`. It currently defaults to `admin` at the DB level, which is unsafe (B4).
- VPN clients relate to users by matching `VpnClient.name` to `User.username` (no FK — B19).
- `VpnClient` and `Certificate` lack uniqueness constraints that would make sync idempotent under concurrency (B20).

## 7. Non-functional requirements & current posture

| Requirement | Intended | Current state |
|-------------|----------|---------------|
| Secrets at rest | Encrypted (AES-256-GCM/HKDF) | ✅ SSH keys, sudo/CA/LDAP passwords, cached `.ovpn` |
| Transport security | TLS to browser | ⚠️ nginx has no TLS configured (I1); rely on external proxy |
| Command injection resistance | `shell=False` + binary whitelist | ✅ (except sudo-path validation gap B14) |
| Horizontal scalability | Multiple workers/replicas | ❌ blocked by in-memory auth state (B6/I6) |
| Rate limiting | Per-IP + per-login | ❌ configured but unimplemented (B5) |
| Auditability | All mutations recorded | ❌ AuditLog never written (B9) |
| Reproducible builds | Locked deps | ⚠️ backend locked; frontend has no committed lockfile (I15) |
| Automated testing/CI | Tests gate merges | ❌ no CI; endpoint coverage partial (B26/F21) |

## 8. Known behavioural deviations (must-read)

These are places where the implementation diverges from what an operator would reasonably expect; each is a backlog item:
- New users without an explicit role become **admin** (B4).
- LDAP login filter is injectable via a crafted username (B10); empty-password binds may succeed on some directories (B11).
- Logout does not revoke the refresh token (B8).
- Rate-limit settings do nothing (B5); the audit log records nothing (B9).
- Certificates *Revoke* and Backup *Create/Restore/Delete* buttons appear for users the API will reject (F16/F17).
- `alembic upgrade` fails on SQLite despite SQLite being suggested for dev (I18).
