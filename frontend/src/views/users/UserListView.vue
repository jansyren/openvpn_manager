<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Users</h1>
      <div class="action-btns">
        <Button label="Add User" icon="pi pi-plus" @click="openAddDialog" />
      </div>
    </div>

    <DataTable :value="users" :loading="loading" striped-rows>
      <template #empty>No users found.</template>
      <Column field="username" header="Username" />
      <Column header="Source">
        <template #body="{ data }">
          <Tag :value="data.auth_source === 'ldap' ? 'AD/LDAP' : 'Local'" :severity="data.auth_source === 'ldap' ? 'info' : 'secondary'" />
        </template>
      </Column>
      <Column header="Role">
        <template #body="{ data }">
          <Tag :value="data.role" :severity="roleSeverity(data.role)" />
        </template>
      </Column>
      <Column header="Active">
        <template #body="{ data }">
          <Tag :value="data.is_active ? 'Active' : 'Inactive'" :severity="data.is_active ? 'success' : 'secondary'" />
        </template>
      </Column>
      <Column header="Superuser">
        <template #body="{ data }">
          <i v-if="data.is_superuser" class="pi pi-check text-success" />
          <span v-else class="text-muted">—</span>
        </template>
      </Column>
      <Column header="Actions" style="width: 14rem">
        <template #body="{ data }">
          <Button
            v-if="data.role === 'vpn_user'"
            icon="pi pi-id-card"
            severity="info"
            text
            rounded
            v-tooltip="'Generate / Renew Certificate'"
            @click="openCertDialog(data)"
          />
          <Button
            v-if="data.role === 'vpn_user'"
            icon="pi pi-eye"
            text
            rounded
            v-tooltip="'Preview Configuration'"
            @click="openPreviewDialog(data)"
          />
          <Button
            icon="pi pi-pencil"
            text
            rounded
            v-tooltip="'Edit'"
            @click="openEditDialog(data)"
          />
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            v-tooltip="'Delete'"
            :disabled="data.id === currentUser?.id"
            @click="confirmDelete(data)"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Add User Dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add User" modal style="width: 460px">
      <div class="field">
        <label>Auth Source *</label>
        <Select
          v-model="addForm.auth_source"
          :options="authSourceOptions"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <div class="field">
        <label>Username *</label>
        <InputText v-model="addForm.username" class="w-full" placeholder="min 3 characters" />
      </div>
      <div v-if="addForm.auth_source === 'local'" class="field">
        <label>Password *</label>
        <InputText v-model="addForm.password" type="password" class="w-full" placeholder="min 8 characters" />
      </div>
      <div v-if="addForm.auth_source === 'ldap'" class="field">
        <label>LDAP Config *</label>
        <Select
          v-model="addForm.ldap_config_id"
          :options="ldapConfigOptions"
          option-label="label"
          option-value="value"
          placeholder="Select LDAP configuration"
          class="w-full"
        />
        <small class="text-muted">User will authenticate against this LDAP directory.</small>
      </div>
      <div class="field">
        <label>Role *</label>
        <Select
          v-model="addForm.role"
          :options="roleOptions"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <div class="field field-inline">
        <Checkbox v-model="addForm.is_active" :binary="true" input-id="add-active" />
        <label for="add-active">Active</label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addDialogVisible = false" />
        <Button label="Create" :loading="saving" @click="createUser" />
      </template>
    </Dialog>

    <!-- Edit User Dialog -->
    <Dialog v-model:visible="editDialogVisible" header="Edit User" modal style="width: 420px">
      <p class="text-muted" style="margin-bottom: 1rem">Editing: <strong>{{ editTarget?.username }}</strong>
        <Tag v-if="editTarget?.auth_source === 'ldap'" value="AD/LDAP" severity="info" style="margin-left: 0.5rem" />
      </p>
      <div v-if="editTarget?.auth_source !== 'ldap'" class="field">
        <label>New Password (leave blank to keep current)</label>
        <InputText v-model="editForm.password" type="password" class="w-full" placeholder="min 8 characters" />
      </div>
      <div class="field">
        <label>Role</label>
        <Select
          v-model="editForm.role"
          :options="roleOptions"
          option-label="label"
          option-value="value"
          class="w-full"
          :disabled="editTarget?.id === currentUser?.id"
        />
        <small v-if="editTarget?.id === currentUser?.id" class="text-muted">Cannot modify your own role</small>
      </div>
      <div class="field field-inline">
        <Checkbox v-model="editForm.is_active" :binary="true" input-id="edit-active" />
        <label for="edit-active">Active</label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editDialogVisible = false" />
        <Button label="Save" :loading="saving" @click="updateUser" />
      </template>
    </Dialog>

    <!-- Generate / Renew Certificate Dialog (vpn_user accounts) -->
    <Dialog v-model:visible="certDialogVisible" :header="`VPN Certificate — ${certUsername}`" modal style="width: 480px">
      <div class="field">
        <label>VPN Instance *</label>
        <Select
          v-model="certInstanceId"
          :options="vpnInstanceOptions"
          option-label="label"
          option-value="value"
          placeholder="Select VPN instance"
          class="w-full"
          @change="onCertInstanceChange"
        />
      </div>

      <p v-if="certLookupLoading" class="text-muted">Checking for an existing certificate…</p>

      <template v-else-if="certInstanceId">
        <Message v-if="certMode === 'revoked'" severity="warn" :closable="false">
          This user's certificate was revoked. Reissuing a revoked certificate isn't
          supported from this page — use VPN Clients to manage it manually.
        </Message>

        <Message v-else-if="certMode === 'import'" severity="info" :closable="false">
          A certificate for this user already exists in the PKI for this instance,
          but isn't linked to a record yet. Import it to enable renew / preview /
          download from this page.
        </Message>

        <template v-else>
          <Message v-if="certMode === 'renew'" severity="info" :closable="false" style="margin-bottom:0.75rem">
            Existing certificate found (serial {{ certExistingClient?.cert_serial?.slice(0, 12) }}…). Renewing will issue a new certificate for the same name.
          </Message>

          <div v-if="!certInstanceHasPassphrase" class="field">
            <label>CA Passphrase *</label>
            <InputText v-model="certPassphrase" type="password" class="w-full" placeholder="Required — no passphrase stored for this instance" />
          </div>
          <Message v-else severity="success" :closable="false" style="margin-bottom:0.75rem">
            This instance has a stored CA passphrase — no passphrase required.
          </Message>

          <div class="field">
            <label>Certificate Expire Days</label>
            <InputNumber v-model="certExpireDays" class="w-full" :min="1" :max="9999" :use-grouping="false" />
          </div>
        </template>
      </template>

      <template #footer>
        <Button label="Close" severity="secondary" @click="certDialogVisible = false" />
        <Button
          v-if="certInstanceId && certMode !== 'revoked'"
          :label="certModeLabel"
          :icon="certMode === 'import' ? 'pi pi-link' : 'pi pi-id-card'"
          :loading="certSaving"
          @click="submitCert"
        />
      </template>
    </Dialog>

    <!-- Preview Configuration Dialog -->
    <Dialog v-model:visible="previewDialogVisible" :header="`Preview Configuration — ${previewUsername}`" modal style="width: 640px">
      <div class="field">
        <label>VPN Instance *</label>
        <Select
          v-model="previewInstanceId"
          :options="vpnInstanceOptions"
          option-label="label"
          option-value="value"
          placeholder="Select VPN instance"
          class="w-full"
          @change="onPreviewInstanceChange"
        />
      </div>

      <p v-if="previewLoading" class="text-muted">Loading configuration…</p>
      <Message v-else-if="previewInstanceId && !previewClient" severity="info" :closable="false">
        No certificate is linked to this user on this instance yet — use Generate / Renew Certificate to create or import one first.
      </Message>
      <Message v-else-if="previewClient?.is_revoked" severity="warn" :closable="false">
        This user's certificate has been revoked and can no longer be downloaded.
      </Message>
      <pre v-else-if="previewContent" class="ovpn-preview">{{ previewContent }}</pre>

      <template #footer>
        <Button label="Close" severity="secondary" @click="previewDialogVisible = false" />
        <Button
          v-if="previewClient && !previewClient.is_revoked"
          label="Download"
          icon="pi pi-download"
          @click="downloadPreview"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import { usersApi } from '@/api/users'
import { ldapApi } from '@/api/ldap'
import { vpnInstancesApi } from '@/api/vpnInstances'
import { clientsApi } from '@/api/clients'
import { certificatesApi } from '@/api/certificates'
import { useAuthStore } from '@/stores/auth'
import type {
  UserManagementRead,
  AppRole,
  AuthSource,
  LdapConfigRead,
  VpnInstanceRead,
  VpnClientRead,
} from '@/types'

const toast = useToast()
const confirm = useConfirm()
const authStore = useAuthStore()
const currentUser = authStore.currentUser

const users = ref<UserManagementRead[]>([])
const ldapConfigs = ref<LdapConfigRead[]>([])
const loading = ref(false)
const saving = ref(false)

const addDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editTarget = ref<UserManagementRead | null>(null)

const addForm = ref({
  username: '',
  password: '',
  role: 'viewer' as AppRole,
  is_active: true,
  auth_source: 'local' as AuthSource,
  ldap_config_id: null as number | null,
})

const editForm = ref({
  password: '',
  role: 'viewer' as AppRole,
  is_active: true,
})

const authSourceOptions = [
  { label: 'Local', value: 'local' },
  { label: 'AD / LDAP', value: 'ldap' },
]

const roleOptions = [
  { label: 'Admin', value: 'admin' },
  { label: 'Operator', value: 'operator' },
  { label: 'Viewer', value: 'viewer' },
  { label: 'VPN User', value: 'vpn_user' },
]

const ldapConfigOptions = ref<{ label: string; value: number }[]>([])

function roleSeverity(role: string): string {
  if (role === 'admin') return 'danger'
  if (role === 'operator') return 'warn'
  if (role === 'vpn_user') return 'success'
  return 'info'
}

async function loadUsers() {
  loading.value = true
  try {
    users.value = await usersApi.list()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load users', life: 4000 })
  } finally {
    loading.value = false
  }
}

async function loadLdapConfigs() {
  try {
    ldapConfigs.value = await ldapApi.listConfigs()
    ldapConfigOptions.value = ldapConfigs.value.map((c) => ({ label: c.name, value: c.id }))
  } catch {
    // LDAP not configured — silently ignore
  }
}

function openAddDialog() {
  addForm.value = { username: '', password: '', role: 'viewer', is_active: true, auth_source: 'local', ldap_config_id: null }
  addDialogVisible.value = true
}

async function createUser() {
  if (!addForm.value.username) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Username is required.', life: 3000 })
    return
  }
  if (addForm.value.auth_source === 'local' && !addForm.value.password) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Password is required for local users.', life: 3000 })
    return
  }
  if (addForm.value.auth_source === 'ldap' && !addForm.value.ldap_config_id) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'LDAP configuration is required.', life: 3000 })
    return
  }
  saving.value = true
  try {
    await usersApi.create({
      username: addForm.value.username,
      password: addForm.value.auth_source === 'local' ? addForm.value.password : undefined,
      role: addForm.value.role,
      is_active: addForm.value.is_active,
      auth_source: addForm.value.auth_source,
      ldap_config_id: addForm.value.ldap_config_id ?? undefined,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: 'User created.', life: 3000 })
    addDialogVisible.value = false
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to create user', life: 4000 })
  } finally {
    saving.value = false
  }
}

function openEditDialog(user: UserManagementRead) {
  editTarget.value = user
  editForm.value = {
    password: '',
    role: user.role as AppRole,
    is_active: user.is_active,
  }
  editDialogVisible.value = true
}

async function updateUser() {
  if (!editTarget.value) return
  saving.value = true
  try {
    const payload: { password?: string; role?: AppRole; is_active?: boolean } = {
      is_active: editForm.value.is_active,
    }
    if (editForm.value.password) payload.password = editForm.value.password
    if (editTarget.value.id !== currentUser?.id) payload.role = editForm.value.role

    await usersApi.update(editTarget.value.id, payload)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'User updated.', life: 3000 })
    editDialogVisible.value = false
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update user', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(user: UserManagementRead) {
  confirm.require({
    message: `Delete user "${user.username}"? This cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await usersApi.delete(user.id)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'User deleted.', life: 3000 })
        await loadUsers()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete user', life: 4000 })
      }
    },
  })
}

// ── Certificate management (vpn_user accounts) ────────────────────────────────
const vpnInstances = ref<VpnInstanceRead[]>([])
const vpnInstanceOptions = computed(() => vpnInstances.value.map((i) => ({ label: i.name, value: i.id })))

async function loadVpnInstances() {
  try {
    vpnInstances.value = await vpnInstancesApi.list()
  } catch {
    vpnInstances.value = []
  }
}

async function findExistingClient(instanceId: number, username: string): Promise<VpnClientRead | null> {
  const clients = await clientsApi.list(instanceId)
  return clients.find((c) => c.name === username && c.client_type === 'user') ?? null
}

const certDialogVisible = ref(false)
const certUsername = ref('')
const certInstanceId = ref<number | null>(null)
const certPassphrase = ref('')
const certExpireDays = ref(825)
const certSaving = ref(false)
const certLookupLoading = ref(false)
const certExistingClient = ref<VpnClientRead | null>(null)
const certPkiExists = ref(false)

const certInstanceHasPassphrase = computed(
  () => vpnInstances.value.find((i) => i.id === certInstanceId.value)?.has_ca_passphrase ?? false,
)

// 'generate': no client record, no PKI cert — issue a brand new one
// 'import':   no client record, but a signed cert already exists in the PKI — link it
// 'renew':    an active client record exists — reissue with the same CN
// 'revoked':  the client record exists but was revoked — not handled from this page
const certMode = computed<'generate' | 'import' | 'renew' | 'revoked'>(() => {
  if (certExistingClient.value?.is_revoked) return 'revoked'
  if (certExistingClient.value) return 'renew'
  if (certPkiExists.value) return 'import'
  return 'generate'
})

const certModeLabel = computed(() => {
  if (certMode.value === 'import') return 'Import'
  if (certMode.value === 'renew') return 'Renew'
  return 'Generate'
})

function openCertDialog(user: UserManagementRead) {
  certUsername.value = user.username
  certInstanceId.value = null
  certPassphrase.value = ''
  certExpireDays.value = 825
  certExistingClient.value = null
  certPkiExists.value = false
  certDialogVisible.value = true
}

async function onCertInstanceChange() {
  certPassphrase.value = ''
  certExistingClient.value = null
  certPkiExists.value = false
  if (!certInstanceId.value) return
  certLookupLoading.value = true
  try {
    const [client, pki] = await Promise.all([
      findExistingClient(certInstanceId.value, certUsername.value),
      vpnInstancesApi.listPkiCerts(certInstanceId.value).catch(() => ({ issued_certs: [] as string[], dh_exists: false })),
    ])
    certExistingClient.value = client
    certPkiExists.value = pki.issued_certs.includes(certUsername.value)
  } catch {
    certExistingClient.value = null
    certPkiExists.value = false
  } finally {
    certLookupLoading.value = false
  }
}

async function submitCert() {
  if (!certInstanceId.value) return
  if (certMode.value !== 'import' && !certInstanceHasPassphrase.value && !certPassphrase.value) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'CA passphrase is required.', life: 3000 })
    return
  }
  certSaving.value = true
  try {
    if (certMode.value === 'import') {
      await clientsApi.create({
        vpn_instance_id: certInstanceId.value,
        name: certUsername.value,
        client_type: 'user',
        import_existing: true,
        require_pam_user: false,
      })
      toast.add({ severity: 'success', summary: 'Imported', detail: `Existing certificate for ${certUsername.value} linked.`, life: 4000 })
    } else if (certMode.value === 'renew' && certExistingClient.value) {
      const existing = certExistingClient.value
      const certs = await certificatesApi.list(certInstanceId.value)
      const cert =
        certs.find((c) => c.common_name === certUsername.value && c.serial === existing.cert_serial) ??
        certs.find((c) => c.common_name === certUsername.value && !c.is_revoked)
      if (!cert) {
        toast.add({ severity: 'error', summary: 'Error', detail: 'Could not locate the existing certificate record.', life: 4000 })
        return
      }
      const result = await certificatesApi.renew(cert.id, certPassphrase.value, certExpireDays.value)
      toast.add({ severity: 'success', summary: 'Renewed', detail: `Certificate renewed. New serial: ${result.serial}`, life: 4000 })
    } else {
      await clientsApi.create({
        vpn_instance_id: certInstanceId.value,
        name: certUsername.value,
        client_type: 'user',
        import_existing: false,
        ca_passphrase: certPassphrase.value || undefined,
        cert_expire_days: certExpireDays.value,
      })
      toast.add({ severity: 'success', summary: 'Certificate generated', detail: `Certificate created for ${certUsername.value}.`, life: 4000 })
    }
    certDialogVisible.value = false
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to save certificate', life: 5000 })
  } finally {
    certSaving.value = false
  }
}

// ── Preview Configuration ─────────────────────────────────────────────────────
const previewDialogVisible = ref(false)
const previewUsername = ref('')
const previewInstanceId = ref<number | null>(null)
const previewLoading = ref(false)
const previewClient = ref<VpnClientRead | null>(null)
const previewContent = ref('')

function openPreviewDialog(user: UserManagementRead) {
  previewUsername.value = user.username
  previewInstanceId.value = null
  previewClient.value = null
  previewContent.value = ''
  previewDialogVisible.value = true
}

async function onPreviewInstanceChange() {
  previewClient.value = null
  previewContent.value = ''
  if (!previewInstanceId.value) return
  previewLoading.value = true
  try {
    const client = await findExistingClient(previewInstanceId.value, previewUsername.value)
    previewClient.value = client
    if (client && !client.is_revoked) {
      previewContent.value = await clientsApi.previewOvpn(client.id)
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load configuration', life: 4000 })
  } finally {
    previewLoading.value = false
  }
}

async function downloadPreview() {
  if (!previewClient.value) return
  try {
    await clientsApi.downloadOvpn(previewClient.value.id, `${previewUsername.value}.ovpn`)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to download config', life: 4000 })
  }
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadLdapConfigs(), loadVpnInstances()])
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}
.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
}
.action-btns {
  display: flex;
  gap: 0.5rem;
}
.field {
  margin-bottom: 1rem;
}
.field label {
  display: block;
  margin-bottom: 0.35rem;
  font-weight: 600;
  font-size: 0.875rem;
}
.field-inline {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.field-inline label {
  margin-bottom: 0;
}
.w-full {
  width: 100%;
}
.text-muted {
  color: var(--p-surface-400);
  font-size: 0.8rem;
}
.text-success {
  color: var(--p-green-500);
}
.ovpn-preview {
  background: var(--p-surface-100);
  border: 1px solid var(--p-surface-300);
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.75rem;
  max-height: 360px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
