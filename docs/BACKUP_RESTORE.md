# Backup & Restore Runbook

_Operational guide for backing up and restoring OpenVPN server configuration and PKI through OpenVPN Manager._

## What a backup contains

A backup is a `.tar.gz` archive captured from a managed server covering its OpenVPN server configuration and Easy-RSA PKI material (as configured for the target VPN instance/server). Archives are stored under the backend's `BACKUP_STORAGE_PATH` (default `./backups`) and tracked in the `backups` table with a SHA-256 hash for integrity verification.

## Permissions

| Action | Endpoint | Required role |
|--------|----------|---------------|
| List backups | `GET /api/v1/backup` | any authenticated user |
| View one | `GET /api/v1/backup/{id}` | any authenticated user |
| Download | `GET /api/v1/backup/{id}/download` | any authenticated user |
| Create | `POST /api/v1/backup` | **admin / superuser** |
| Restore | `POST /api/v1/backup/{id}/restore` | **admin / superuser** |
| Delete | `DELETE /api/v1/backup/{id}` | **admin / superuser** |

In the UI, the Backup page and its Create/Restore/Delete buttons are shown only to admin-capable users; the route itself is admin-guarded.

## Creating a backup (UI)

1. Log in as an admin.
2. Open **Backup** in the sidebar.
3. Click **Create Backup**, choose the target server/instance, and confirm.
4. The new archive appears in the list with its timestamp and size. Download it and store it off-box — see the warning below.

## Restoring a backup (UI)

1. Log in as an admin and open **Backup**.
2. Find the archive to restore and click the **Restore** (history) icon.
3. Confirm. The backend verifies the archive's SHA-256 hash before extracting, and guards against tar path-traversal entries. A restore overwrites the target server's configuration/PKI with the archive's contents.
4. After a config/PKI restore, restart the affected VPN instance(s) from the VPN Instances view so OpenVPN reloads the restored files.

## Important operational notes

- **Store archives off the application host.** By default archives live inside `BACKUP_STORAGE_PATH` on the backend host. Copy them to secure off-host storage; do **not** leave customer PKI archives inside the source/repo tree.
- **Archives contain private key material.** Treat them as secrets: restrict filesystem permissions and transport them only over encrypted channels.
- **Retention.** `BACKUP_MAX_RETENTION_DAYS` (default 30) governs how long archives are retained; adjust to your policy.
- **Restore is destructive.** It replaces live configuration/PKI on the target. Take a fresh backup immediately before restoring, so you can roll back.
- **Integrity.** Restore refuses an archive whose SHA-256 does not match the recorded hash; re-download or re-create if verification fails.

## CLI / manual fallback

If the UI is unavailable, archives under `BACKUP_STORAGE_PATH` are plain `.tar.gz` files and can be inspected/extracted with standard tools (`tar tzf <archive>` to list, `tar xzf` to extract) on the server. Recreate the corresponding `backups` table row only if you need the manager UI to track a manually-placed archive.
