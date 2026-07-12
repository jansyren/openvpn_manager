# OpenVPN Manager — Architecture Review

_Review date: 2026-07-12. Scope: full application (backend, frontend, infrastructure) at the `main` branch. This document describes the system as built and assesses it; concrete remediation items are tracked in [IMPROVEMENTS.md](./IMPROVEMENTS.md) and the intended behaviour is captured in [SPECIFICATION.md](./SPECIFICATION.md)._

## 1. What the system is

OpenVPN Manager is a web application for centrally managing one or more OpenVPN servers — their configuration, PKI/certificates, client profiles, routes, PAM users, LDAP/AD integration, and backups — across local and SSH-reachable remote hosts. It is a three-tier application:

```
Vue 3 SPA (PrimeVue 4, Pinia, Vue Router)
      │  /api/v1  (JWT bearer + refresh cookie)
FastAPI backend (async SQLAlchemy, Pydantic v2)
      │                    │                       │
  PostgreSQL         SSH (asyncssh)           local exec / file I/O
                     to remote servers
```

The backend never touches OpenVPN directly through a library; it drives the real hosts by executing whitelisted binaries (`openvpn`, `easyrsa`, `systemctl`, etc.) either locally or over SSH through a common `Executor` abstraction.

## 2. Backend architecture

### Layering
The intended shape is `routers/ → services/ → db/models/`, with `services/remote/` providing local-vs-remote command execution. This discipline mostly holds: `services/` contains cohesive, well-separated modules (`auth_service`, `ldap_service`, `easyrsa_service`, `client_generator`, `config_parser`, the executor abstraction), and `core/` isolates security, logging, and the exception hierarchy.

The discipline breaks in a handful of **fat routers** that inline orchestration that belongs in a service. The clearest example is `routers/ldap.py::sync_ldap_users` — a ~167-line handler that searches LDAP, creates users, creates VPN clients, issues certificates, and inserts certificate records inline. `routers/vpn_instances.py` (~505 LOC), `routers/clients.py`, `routers/easyrsa.py`, and `routers/pam.py` follow the same pattern to a lesser degree. This is the single largest structural debt in the backend (see IMPROVEMENTS B1).

A smaller repeated pattern: five different modules re-implement "select a row or raise 404" (`_get_config_or_404`, `_get_instance_or_404`, `_get_instance_for_cert`, `get_server`, …). One generic helper would remove the duplication (B2).

### Authentication & authorization
- **Tokens**: RS256 JWT. Short-lived access token (15 min) returned in the response body and held in memory by the SPA; a 7-day refresh token in an httpOnly, `SameSite=Strict` cookie scoped to `/api/v1/auth`.
- **Roles**: a user carries a full *set* of roles (`user_roles` table), each tagged with a `source` (`ldap` vs `manual`). For LDAP users the `ldap`-sourced roles are recomputed from AD group membership on every login; `manual` roles (admin-assigned) survive that recompute. The JWT carries an `active_role` claim, and users with more than one role can switch which role is active via `POST /auth/switch-role` without re-authenticating. Authorization dependencies (`get_current_operator`, `get_current_superuser`) read the *active role* from the token, not the raw DB column.
- This role model is a genuine strength — it is coherent, well-tested, and cleanly separates "what roles you have" from "which role you are acting as." It is the most mature part of the codebase.

### Remote execution & security boundary
All command execution goes through `services/remote/base.py`, which enforces `shell=False` (local) / `shlex`-quoted argument lists (remote) against an `ALLOWED_BINARIES` whitelist. Secrets (SSH private keys, sudo/CA/LDAP passwords) are encrypted at rest with AES-256-GCM using HKDF-derived keys rooted in `SSH_KEY_ENCRYPTION_SECRET`. Passwords are passed to child processes via stdin, never as argv. This is a well-considered boundary. Two caveats: the whitelist validates only `argv[0]`, so the real binary invoked *under* `sudo` is never checked (B14, not currently exploitable), and the LDAP search filter interpolates the raw login username without RFC-4515 escaping (B10, an injection risk that should be fixed).

### State & persistence
- **Database**: PostgreSQL in production via async SQLAlchemy; the test suite uses in-memory SQLite with `Base.metadata.create_all` (not migrations). Note that several Alembic migrations use operations SQLite cannot perform (`ALTER … ADD CONSTRAINT`), so `alembic upgrade` does **not** work on SQLite despite docs implying SQLite is a dev option (I18).
- **In-memory server state**: the token blacklist and the login-lockout tracker are plain in-process dicts (`core/security.py`). This is the most consequential runtime constraint in the system: it silently breaks with more than one Uvicorn worker or more than one replica (a token revoked on one worker stays valid on another; lockout resets on restart), and it is undocumented. The `users.failed_logins` / `locked_until` columns that would persist lockout exist but are unused (B6/I6).

### Data model
Eight core models plus join tables. Relationships and cascade choices are mostly sound. Two fragilities stand out: VPN clients are linked to users by a *string convention* (`VpnClient.name == User.username`) rather than a foreign key (B19), and `VpnClient`/`Certificate` lack the unique constraints that would make the LDAP-sync "create if absent" logic race-safe (B20).

## 3. Frontend architecture

A Vue 3 + TypeScript SPA using PrimeVue 4, Pinia, and Vue Router. Strengths: strict typing throughout (**zero `any`** in `src/`), an Axios client with a clean JWT-injection + 401-auto-refresh interceptor, and route guards that mirror the backend's role model (`requiresAdmin`/`requiresOperator`, plus a hard-lock of vpn-user-only accounts to the self-service portal).

The main architectural weaknesses are consistency and size:

- **State management is split-brain.** Only three Pinia stores exist (`servers`, `context`, `auth`); the other ~15 feature views each fetch into local `ref`s on mount. `context.ts` now reads servers reactively from the servers store, but still keeps its **own independent copy of VPN instances**, so the global instance selector can go stale until explicitly refreshed (F2/F3).
- **Error handling is copy-pasted.** The `(e as { detail?: string }).detail ?? '…'` toast pattern appears roughly **80 times** across 16 views. `client.ts` already normalizes errors to `{status, detail}`; a single `useApiToast` composable would delete most of this (F5).
- **A few monster components.** Five views exceed 400 lines and together are ~57% of all view code: `VpnInstanceDetailView.vue` (~1185), `EasyRsaSettingsView.vue` (~831), `PamUserManagerView.vue` (~745), `UserListView.vue` (~689), `VpnInstanceListView.vue` (~461). Repeated UI (page header, confirm-delete, CA-passphrase field, server/instance selector) is inlined rather than extracted (F9/F10).
- **Two real permission gaps.** The Certificates view's *Revoke* button and the Backup view's *Create/Restore/Delete* buttons render for all authenticated users, but the corresponding endpoints require superuser — so lower-privileged users see enabled controls that 403 (F16/F17). These are the only correctness-affecting frontend findings.
- **Styling duplication.** `.page-header` / `.field` / `.page-title` CSS is redefined in ~14 separate scoped blocks (F19).

## 4. Infrastructure & delivery

- **Docker Compose** brings up PostgreSQL, backend, and frontend. Gaps: the frontend maps `12443:443` but nginx only listens on `:80` with no TLS configured, so that port is dead (I1); only the database has a healthcheck (I2); the backend container runs as root (I5); and migrations run on every container start with no locking (I4).
- **No CI/CD exists** — no GitHub Actions, GitLab CI, or pre-commit. A `docker-compose.test.yml` exists but nothing invokes it (I9). There is no committed `package-lock.json`, and the Dockerfile uses `npm install` rather than `npm ci`, so frontend builds are not reproducible (I15).
- **Dependency hygiene**: backend deps are unbounded (`>=`, no upper cap); `uv.lock` pins the actual tree. Frontend depends on the deprecated `@primevue/themes` package (I13/I14).
- **Repo hygiene** is the most surprising infra issue: a screenshot PNG and a 272 KB `man_openvpn.txt` are git-tracked (I20), and — more seriously — the working tree's `backups/` directory contains **real customer backup archives** (Bahrain/Mumbai `.tar.gz`, root-owned) sitting inside the repo checkout (I21). No secrets are tracked (verified), but the customer data should not live here.
- **Docs**: the README is genuinely good (setup, RBAC, a 6-step LDAP guide). Missing: a standalone architecture doc (this file), a backup/restore runbook, and a note about the SQLite-migration caveat (I12).

## 5. Overall assessment

This is a well-conceived application with a notably mature auth/role subsystem and a disciplined command-execution security boundary. The debt is concentrated and addressable, not systemic:

1. **Security correctness** — role-defaults-to-admin, LDAP filter injection, refresh-token not revoked on logout, unimplemented rate limiting, and the two unguarded frontend buttons. These are the priority.
2. **Operational robustness** — in-memory auth state blocks horizontal scaling; no CI; non-reproducible builds; customer data in the working tree.
3. **Maintainability** — fat routers, ~80× duplicated error handling, five oversized views, and an unwritten audit log.

None of these require re-architecture. They are well-suited to being picked off individually — see the prioritized, self-contained backlog in [IMPROVEMENTS.md](./IMPROVEMENTS.md).
