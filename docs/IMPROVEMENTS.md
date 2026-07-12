# OpenVPN Manager — Improvement Backlog

_Prioritized, self-contained work items from the 2026-07-12 full review. Each item is scoped so a single subagent can implement it in isolation: it names the files, states the problem and the fix, and gives an acceptance check. IDs (B#/F#/I#) match the source findings referenced in [ARCHITECTURE.md](./ARCHITECTURE.md) and [SPECIFICATION.md](./SPECIFICATION.md)._

**How to use this doc:** pick an item, read its "Files"/"Fix"/"Acceptance". Items are grouped by priority. Items marked _[independent]_ touch disjoint files and can run in parallel; items marked _[shared: X]_ touch file X and should not run concurrently with siblings that share it. Backend test runs need JWT test keys + a `.env` (see `backend/generate_test_keys.py` and `.env.example`); frontend checks need Node ≥18 (`npm run build`, `npm run type-check`).

---

## P0 — Security correctness (do first)

### SEC-1 (B4) — `User.role` must not default to `admin` _[independent]_
- **Files:** `backend/app/db/models/user.py` (line ~20), new Alembic migration under `backend/alembic/versions/`, `backend/app/tests/conftest.py`.
- **Problem:** `role` column has `default="admin"`/`server_default="admin"`. Any insert omitting `role` silently creates an admin. This is also the root cause of the failing `test_create_server_requires_superuser`.
- **Fix:** change the model default and `server_default` to `"vpn_user"`; add a migration altering the column default. Audit every `User(...)` construction (`cli.py`, `auth_service.py`, `routers/users.py`, `routers/ldap.py`) to pass an explicit role. Fix the `regular_user` fixture in `conftest.py` to set `role="viewer"` (or similar) explicitly.
- **Acceptance:** `uv run pytest` — `test_create_server_requires_superuser` now passes; a new test asserts a `User()` built without a role is not admin.

### SEC-2 (B10) — Escape the LDAP search filter _[independent]_
- **Files:** `backend/app/services/ldap_service.py` (`_do_authenticate`, line ~69).
- **Problem:** `f"(&{config.user_filter}({config.username_attr}={username}))"` interpolates the raw login username → LDAP filter injection.
- **Fix:** escape `username` with `ldap3.utils.conv.escape_filter_chars(username)` before interpolation. (Leave `user_filter`/`username_attr` — they are admin-configured, not user input.)
- **Acceptance:** add a unit test that a username like `*)(uid=*` is escaped in the constructed filter; existing LDAP tests still pass.

### SEC-3 (B11) — Reject empty-password LDAP binds _[independent]_
- **Files:** `backend/app/services/ldap_service.py` (`_do_authenticate`), `backend/app/schemas/auth.py`.
- **Problem:** an empty password can produce a successful *anonymous* bind on many directories → auth bypass.
- **Fix:** guard against empty/whitespace password before the user bind in `_do_authenticate` (raise the same auth error); confirm `LoginRequest.password` has `min_length=1`.
- **Acceptance:** unit test that an empty password never reaches a successful bind path.

### SEC-4 (B8) — Blacklist the refresh token on logout & password change _[shared: routers/auth.py]_
- **Files:** `backend/app/routers/auth.py` (`logout`, `change_my_password`), possibly `core/security.py`.
- **Problem:** logout blacklists only the access-token JTI; the 7-day refresh token stays valid. Password change likewise only revokes the current access token.
- **Fix:** on logout, read the refresh cookie, decode it, and `blacklist_token(jti, exp)` for the refresh JTI too (best-effort, wrapped in try/except) before clearing the cookie. On password change, also revoke the caller's refresh token.
- **Acceptance:** integration test: after logout, reusing the refresh cookie against `/auth/refresh` returns 401.

### SEC-5 (F16/F17) — Gate privileged buttons in the SPA _[independent]_
- **Files:** `frontend/src/views/certificates/CertificateManagerView.vue`, `frontend/src/views/backup/BackupRestoreView.vue`, `frontend/src/router/index.ts`, `frontend/src/layouts/DefaultLayout.vue`.
- **Problem:** the Certificates *Revoke* button and Backup *Create/Restore/Delete* buttons render for all users, but the endpoints are superuser-only → users see controls that 403.
- **Fix:** add `v-if="authStore.canAdminister"` to those buttons; add `meta: { requiresAdmin: true }` to the `/backup` route and gate the Backup nav item on `canAdminister` (certificates listing can stay visible, but hide/disable revoke). Verify against backend gates in `certificates.py`/`backup.py` — if any endpoint is strict `is_superuser` rather than admin-role, prefer a dedicated `canManageBackups`/superuser check to avoid the admin-role-vs-superuser mismatch (see SEC-9).
- **Acceptance:** `npm run build` clean; an operator/viewer no longer sees enabled Revoke/Create/Restore/Delete controls.

### SEC-6 (B5) — Implement rate limiting (or remove the dead settings) _[shared: main.py]_
- **Files:** `backend/app/main.py`, `backend/app/config.py`, deps in `pyproject.toml`.
- **Problem:** `rate_limit_per_minute` / `login_rate_limit_per_minute` exist but nothing enforces them.
- **Fix:** add `slowapi` (or an equivalent middleware), wire a global limiter from `rate_limit_per_minute` and a stricter limiter on `/auth/login` from `login_rate_limit_per_minute`, keyed on client IP (reuse `get_client_ip`). Document the trusted-proxy assumption. If out of scope, at minimum delete the settings and note it — do not leave dead security config.
- **Acceptance:** a test firing >limit requests to `/auth/login` gets 429; normal traffic unaffected.

---

## P1 — Operational robustness

### OPS-1 (B6/I6) — Move auth state out of process memory _[shared: core/security.py]_
- **Files:** `backend/app/core/security.py` (`_TOKEN_BLACKLIST`, `_LOCKOUT_TRACKER`), `config.py`, `docker-compose.yml`, `entrypoint.sh`.
- **Problem:** token blacklist and lockout are per-process dicts → break with >1 worker/replica and reset on restart. `users.failed_logins`/`locked_until` columns are unused.
- **Fix (choose one, document it):** (a) introduce Redis and store blacklist JTIs + lockout counters there; or (b) persist lockout to the existing `users` columns and blacklist to a small DB table. Then it is safe to run multiple workers. Update compose (add Redis if chosen) and note the constraint's removal.
- **Acceptance:** blacklist/lockout survive a simulated second worker (or a restart in the DB variant); existing auth tests pass.

### OPS-2 (I15/I10) — Commit a frontend lockfile & use `npm ci` _[independent]_
- **Files:** `frontend/package-lock.json` (new), `frontend/Dockerfile`.
- **Problem:** no committed lockfile; Dockerfile uses `npm install` → non-reproducible builds and no `npm ci` in CI.
- **Fix:** generate and commit `package-lock.json`; change the Dockerfile to `npm ci`.
- **Acceptance:** `npm ci` succeeds against the committed lockfile; Docker build still works.

### OPS-3 (I9/I10) — Add a minimal CI pipeline _[independent]_
- **Files:** `.github/workflows/ci.yml` (new).
- **Problem:** no automated checks on push/PR.
- **Fix:** a workflow with two jobs. **Backend:** set up Python + `uv`, generate JWT test keys, export the test env, run `ruff`, `mypy`, `uv run pytest`. **Frontend:** `npm ci`, `npm run type-check`, `npm run build`, `npm run test:unit`. Depends on OPS-2 for `npm ci`.
- **Acceptance:** workflow is green on a clean checkout (allowing for the two known-failing tests only if SEC-1/QA-1 not yet merged — otherwise fully green).

### OPS-4 (I21/I20) — Remove customer data and binary clutter from the repo _[independent]_
- **Files:** working tree `backups/` (root-owned archives), tracked `Screenshot from 2026-03-29 14-31-38.png`, tracked `man_openvpn.txt`; `.gitignore` already covers `backups/`.
- **Problem:** real customer backup archives (Bahrain/Mumbai `.tar.gz`) sit in the checkout's `backups/`; a screenshot and a 272 KB man-page dump are git-tracked.
- **Fix:** `git rm --cached` the screenshot and `man_openvpn.txt` (delete or relocate to `docs/` if genuinely needed); move the real `backups/` archives out of the repo directory entirely (they are gitignored but should not live in a source tree). **Do not commit any customer archive.**
- **Acceptance:** `git ls-files` shows no stray PNG/large txt; `backups/` holds no customer data inside the repo.

### OPS-5 (I1) — Fix or remove the dead frontend TLS port _[independent]_
- **Files:** `frontend/nginx.conf`, `docker-compose.yml`, `frontend/Dockerfile`.
- **Problem:** compose publishes `12443:443` but nginx only listens on `:80` — TLS is not terminated anywhere.
- **Fix:** either add a real `listen 443 ssl` server block with mounted certs (and document cert provisioning) or drop the `12443:443` mapping and document that TLS is terminated by an external proxy. Add gzip while there (I3).
- **Acceptance:** compose config matches nginx reality; no dead published port.

---

## P2 — Maintainability & correctness cleanups

### QA-1 (B25) — Fix the wrong SHA-256 literal in the test _[independent]_
- **Files:** `backend/app/tests/unit/test_security.py` (line ~36).
- **Fix:** replace the typo'd expected hash with the correct `sha256("hello world")` = `b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9`.
- **Acceptance:** `uv run pytest app/tests/unit/test_security.py` passes.

### REF-1 (B1) — Extract LDAP sync orchestration into a service _[shared: routers/ldap.py]_
- **Files:** `backend/app/routers/ldap.py` (`sync_ldap_users`, `deploy_ldap_auth`), new `backend/app/services/ldap_sync_service.py`.
- **Problem:** ~167-line handler mixing LDAP search, user/client creation, and cert issuance.
- **Fix:** move the orchestration into a service function the router calls; keep the router thin (parse request, call service, shape response).
- **Acceptance:** behaviour unchanged; a service-level test exercises the two-pass group accumulation directly.

### REF-2 (B2) — Single `get_or_404` helper _[independent]_
- **Files:** new helper in `backend/app/db/` or `dependencies.py`; call sites in `routers/ldap.py`, `routers/easyrsa.py`, `routers/certificates.py`, `services/server_service.py`.
- **Fix:** add `async def get_or_404(db, Model, id, name=None) -> Model` raising `NotFoundError`; replace the per-module re-implementations.
- **Acceptance:** existing tests pass; duplication removed.

### REF-3 (F5/F10) — Shared frontend error-toast composable + UI primitives _[independent]_
- **Files:** new `frontend/src/composables/useApiToast.ts`, new `frontend/src/components/PageHeader.vue`; refactor a first batch of views.
- **Problem:** the `(e as { detail?: string }).detail ?? '…'` pattern appears ~80×; page-header/confirm-delete markup is duplicated across ~14 views.
- **Fix:** add `useApiToast()` wrapping the existing normalized error shape; add `PageHeader.vue`. Migrate 3–4 views as a proof, leaving a short migration note for the rest (can be follow-up items per view).
- **Acceptance:** `npm run build` clean; migrated views behave identically with far less boilerplate.

### REF-4 (B15) — Run bcrypt off the event loop _[shared: auth_service.py]_
- **Files:** `backend/app/core/security.py` and/or `backend/app/services/auth_service.py`.
- **Problem:** `hash_password`/`verify_password` (bcrypt, ~100ms) run synchronously inside async handlers, stalling the loop under login load.
- **Fix:** wrap the bcrypt calls in `run_in_executor` (or `anyio.to_thread.run_sync`) at the call sites in `authenticate`, `change_password`, `create_user`.
- **Acceptance:** login flow unchanged functionally; calls no longer block the loop (a simple concurrency test or manual reasoning documented).

### DATA-1 (B20/B19) — Add uniqueness constraints and consider a client→user FK _[independent]_
- **Files:** new Alembic migration; `backend/app/db/models/vpn_client.py`, `certificate.py`.
- **Fix:** add `UniqueConstraint(vpn_instance_id, name)` on `VpnClient` and `UniqueConstraint(vpn_instance_id, serial)` on `Certificate`, making LDAP-sync creation idempotent under concurrency. Optionally introduce a nullable FK from `VpnClient` to `User` to replace the string-convention join (larger change — can be split out).
- **Acceptance:** migration applies on PostgreSQL; sync run twice does not create duplicates.

### AUDIT-1 (B9) — Write to the AuditLog (or remove it) _[shared: many routers]_
- **Files:** `backend/app/db/models/audit_log.py` consumers; a small `audit_service` + calls in mutating routers.
- **Problem:** `AuditLog` is defined and exposed via `/system` but never written — the audit trail is empty.
- **Fix:** add an `audit_service.record(db, user, action, entity, old, new)` helper and call it from the key mutation paths (user role changes, server/instance/client create/delete, backup restore, LDAP sync). If auditing is not wanted, remove the model and its `/system` endpoints instead of shipping a dead feature.
- **Acceptance:** a mutation produces an `AuditLog` row visible via `/system`; a test asserts it.

### CFG-1 (B23/B12) — Harden config defaults _[independent]_
- **Files:** `backend/app/config.py`, `backend/app/db/models/ldap_config.py`, `backend/app/schemas/ldap.py`.
- **Fix:** validate `ssh_key_encryption_secret` is set and non-trivial (it roots all secret encryption); make `is_production` also force `app_debug=False`; cache the JWT PEM reads. Consider defaulting `tls_verify_cert` to `True` for new LDAP configs (with a clearly-labelled opt-out).
- **Acceptance:** startup fails fast on a missing/weak encryption secret; tests updated.

### DOC-1 (I12/I18) — Add architecture, runbook, and SQLite caveat docs _[independent]_
- **Files:** this `docs/` set (already added), plus a backup/restore runbook and a note in `README.md`/`CLAUDE.md` that `alembic upgrade` requires PostgreSQL (SQLite is test-only).
- **Acceptance:** README no longer implies SQLite works for migrations; a backup/restore runbook exists.

---

## P3 — Nice to have

- **NTH-1 (F6):** fix `frontend/src/api/client.ts:8` — import `AxiosResponse` as `type` to clear the vite build warning. _[independent, tiny]_
- **NTH-2 (F19):** extract the repeated `.page-header`/`.field`/`.page-title` CSS into a shared stylesheet. _[independent]_
- **NTH-3 (F2/F3):** finish unifying `context.ts` — derive VPN instances from a store instead of a private copy, removing the manual `refreshInstances()` calls. _[shared: context.ts]_
- **NTH-4 (I13/I14):** add upper bounds to backend deps; migrate off the deprecated `@primevue/themes` package. _[independent]_
- **NTH-5 (F9):** split the five >400-line views (start with `VpnInstanceDetailView.vue`) into subcomponents. _[independent, one item per view]_
- **NTH-6 (B14):** validate the real binary under `sudo` in `services/remote/base.py`, not just `argv[0]`. _[independent]_
- **NTH-7 (B13):** unlink the LDAP CA temp file after use in `ldap_service._make_server`. _[independent]_
- **NTH-8 (I22):** make `backend/generate_test_keys.py` write relative paths so local (non-container) test runs work. _[independent]_
- **NTH-9 (B26/F21):** raise endpoint test coverage for the untested privileged routers (easyrsa, pam, backup, deploy, vpn_instances, clients, certificates). _[independent, one item per router]_
- **NTH-10 (I2/I5):** add backend/frontend Docker healthchecks; run the backend container as a non-root `USER`. _[independent]_

---

## Suggested execution order for a subagent fleet

1. **Wave 1 (parallel, independent):** SEC-1, SEC-2, SEC-3, SEC-5, QA-1, OPS-4, NTH-1.
2. **Wave 2:** SEC-4 and SEC-6 (each owns one shared file); OPS-2 then OPS-3 (CI depends on the lockfile); REF-2, DATA-1, CFG-1, DOC-1, OPS-5.
3. **Wave 3:** OPS-1, REF-1, REF-3, REF-4, AUDIT-1 (larger, mostly single-shared-file each).
4. **Wave 4:** the P3 polish items, one per view/router where noted.
