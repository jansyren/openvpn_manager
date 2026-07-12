// ── System ────────────────────────────────────────────────────────────────
export interface SystemInfo {
  app_version: string
  git_commit: string
  build_time: string
  openvpn_version: string | null
  python_version: string
  environment: string
}

// ── Auth ──────────────────────────────────────────────────────────────────
export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface UserRead {
  id: number
  username: string
  role: string
  is_active: boolean
  is_superuser: boolean
  roles: string[]
  active_role: string
}

export interface UserManagementRead {
  id: number
  username: string
  role: string
  is_active: boolean
  is_superuser: boolean
  auth_source: string
}

export type AppRole = 'admin' | 'operator' | 'viewer' | 'vpn_user'
export type AuthSource = 'local' | 'ldap'

export interface UserCreate {
  username: string
  password?: string
  role: AppRole
  is_active?: boolean
  auth_source?: AuthSource
  ldap_config_id?: number
}

export interface UserUpdate {
  password?: string
  role?: AppRole
  is_active?: boolean
}

// ── Servers ──────────────────────────────────────────────────────────────
export interface ServerRead {
  id: number
  name: string
  is_local: boolean
  host: string | null
  port: number
  ssh_username: string | null
  ssh_host_fingerprint: string | null
  description: string | null
  use_sudo: boolean
  has_sudo_password: boolean
}

export interface ServerCreate {
  name: string
  is_local: boolean
  host?: string
  port?: number
  ssh_username?: string
  ssh_private_key_pem?: string
  description?: string
  use_sudo?: boolean
  sudo_password?: string
}

export interface ServerTestConnectionResult {
  success: boolean
  message: string
  fingerprint: string | null
}

export interface DiscoveredConfig {
  path: string
  name: string
  size_bytes: number
  port: number | null
  proto: string | null
  dev: string | null
  network: string | null
  netmask: string | null
}

// ── VPN Instances ─────────────────────────────────────────────────────────
export interface VpnInstanceRead {
  id: number
  server_id: number
  name: string
  config_path: string
  proto: string
  port: number
  dev: string
  network: string | null
  netmask: string | null
  status: string
  easyrsa_path: string | null
  easyrsa_server_id: number | null
  pam_enabled: boolean
  enforce_cn_username: boolean
  tls_auth_key: string | null
  has_ca_passphrase: boolean
  ldap_auth_enabled: boolean
  ldap_config_id: number | null
}

export interface VpnInstanceCreate {
  server_id: number
  name: string
  config_path: string
  proto?: 'udp' | 'tcp'
  port?: number
  dev?: string
  network?: string
  netmask?: string
  easyrsa_path?: string
  easyrsa_server_id?: number
  pam_enabled?: boolean
  import_existing?: boolean
}

export interface VpnInstanceUpdate {
  pam_enabled?: boolean
  enforce_cn_username?: boolean
  tls_auth_key?: string | null
  ldap_auth_enabled?: boolean
  ldap_config_id?: number | null
  ca_passphrase?: string | null
}

export interface VpnInstanceStatus {
  instance_id: number
  name: string
  status: string
  active_since: string | null
  pid: number | null
}

export type ServiceAction = 'start' | 'stop' | 'restart' | 'reload' | 'enable' | 'disable'

export interface DirectiveSpec {
  name: string
  description: string
  directive_type: 'flag' | 'single' | 'multi'
  default: string | null
  allowed_values: string[] | null
  example: string | null
  deprecated: boolean
  category: string
  mutually_exclusive_with: string[]
}

// ── Routes ────────────────────────────────────────────────────────────────
export interface RouteRead {
  id: number
  server_id: number
  source_tun: string
  dest_tun: string
  destination_network: string
  metric: number
  is_persistent: boolean
  is_active: boolean
}

export interface RouteCreate {
  server_id: number
  source_tun: string
  dest_tun: string
  destination_network: string
  metric?: number
  is_persistent?: boolean
}

export interface LiveRoutingTable {
  server_id: number
  routes: string[]
}

// ── Clients ───────────────────────────────────────────────────────────────
export interface VpnClientRead {
  id: number
  vpn_instance_id: number
  name: string
  client_type: 'user' | 'site'
  email: string | null
  cert_serial: string | null
  is_revoked: boolean
}

export interface VpnClientCreate {
  vpn_instance_id: number
  name: string
  client_type: 'user' | 'site'
  email?: string
  ca_passphrase?: string
  cert_expire_days?: number
  pam_password?: string
  pam_groups?: string[]
  import_existing?: boolean
  require_pam_user?: boolean
}

// ── Certificates ──────────────────────────────────────────────────────────
export interface CertificateRead {
  id: number
  vpn_instance_id: number
  common_name: string
  serial: string
  cert_type: 'ca' | 'server' | 'client'
  not_before: string | null
  not_after: string | null
  is_revoked: boolean
  revoked_at: string | null
  revoke_reason: string | null
}

// ── Easy-RSA ──────────────────────────────────────────────────────────────
export interface EasyRsaSettings {
  easyrsa_path: string | null
  pki_dir: string | null
  easyrsa_server_id: number | null
  easyrsa_use_sudo: boolean
  pki_initialized: boolean
  ca_built: boolean
  permission_error: boolean
  error_detail: string | null
}

// ── PAM ───────────────────────────────────────────────────────────────────
export interface PamUserRead {
  username: string
  groups: string[]
  uid: number | null
}

export interface PamGroupRead {
  name: string
  gid: number | null
  members: string[]
}

export interface StoredPamUserRead {
  id: number
  server_id: number
  username: string
  groups: string[]
  has_hash: boolean
}

export interface StoredPamGroupRead {
  id: number
  server_id: number
  name: string
  gid: number | null
}

export interface PamGroupCreate {
  name: string
  gid?: number | null
}

export interface PamCopyRequest {
  source_server_id: number
  target_server_id: number
  include_groups: boolean
}

export interface PamCopyResult {
  groups_created: number
  groups_skipped: number
  groups_failed: string[]
  users_created: number
  users_skipped: number
  users_failed: string[]
}

// ── Backup ────────────────────────────────────────────────────────────────
export interface BackupRead {
  id: number
  server_id: number | null
  filename: string
  size_bytes: number | null
  sha256: string
  backup_type: string
  notes: string | null
  created_at: string
}

export interface BackupCreate {
  server_id: number
  backup_type: 'full' | 'easyrsa' | 'server_config'
  notes?: string
}

// ── Deploy ────────────────────────────────────────────────────────────────
export interface DeployPrerequisites {
  server_id: number
  os_compatible: boolean
  os_version: string | null
  openvpn_installed: boolean
  easyrsa_installed: boolean
  disk_space_gb: number | null
  ready_to_deploy: boolean
  notes: string[]
}

export interface DeployTaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  log_lines: string[]
  error: string | null
}

// ── LDAP ─────────────────────────────────────────────────────────────────
export interface LdapConfigRead {
  id: number
  name: string
  server_url: string
  server_url_backup: string | null
  bind_dn: string
  user_search_base: string
  user_filter: string
  username_attr: string
  group_search_base: string | null
  group_member_attr: string
  use_tls: boolean
  tls_verify_cert: boolean
  ca_cert_pem: string | null
  is_active: boolean
}

export interface LdapConfigCreate {
  name: string
  server_url: string
  server_url_backup?: string
  bind_dn: string
  bind_password: string
  user_search_base: string
  user_filter?: string
  username_attr?: string
  group_search_base?: string
  group_member_attr?: string
  use_tls?: boolean
  tls_verify_cert?: boolean
  ca_cert_pem?: string
  is_active?: boolean
}

export interface LdapConfigUpdate {
  name?: string
  server_url?: string
  server_url_backup?: string
  bind_dn?: string
  bind_password?: string
  user_search_base?: string
  user_filter?: string
  username_attr?: string
  group_search_base?: string
  group_member_attr?: string
  use_tls?: boolean
  tls_verify_cert?: boolean
  ca_cert_pem?: string
  is_active?: boolean
}

export interface LdapGroupRoleMappingRead {
  id: number
  ldap_config_id: number
  group_dn: string
  role: AppRole
}

export interface LdapGroupRoleMappingCreate {
  group_dn: string
  role: AppRole
}

export interface VpnInstanceLdapGroupRead {
  id: number
  vpn_instance_id: number
  ldap_config_id: number
  group_dn: string
  display_name: string | null
}

export interface VpnInstanceLdapGroupCreate {
  ldap_config_id: number
  group_dn: string
  display_name?: string
}

export interface LdapTestResult {
  success: boolean
  message: string
}

export interface LdapSyncResult {
  users_created: number
  clients_created: number
  certs_issued: number
  skipped: number
  failed: string[]
}

export interface LdapDeployResult {
  script_path: string
  config_path: string
  config_directives: string
}

// ── System ────────────────────────────────────────────────────────────────
export interface AuditLogEntry {
  id: number
  user_id: number | null
  action: string
  resource_type: string
  resource_id: string | null
  detail_json: string | null
  ip_address: string | null
  created_at: string
}
