<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">VPN Clients</h1>
      <div class="action-btns">
        <Button label="Add Client" icon="pi pi-plus" :disabled="!selectedInstanceId" @click="openAddDialog" />
      </div>
    </div>

    <div class="filter-bar">
      <Select
        v-model="selectedServerId"
        :options="serverOptions"
        option-label="label"
        option-value="value"
        placeholder="Select Server"
        show-clear
        class="filter-select"
        @change="onServerChange"
      />
      <Select
        v-model="selectedInstanceId"
        :options="instanceOptions"
        option-label="label"
        option-value="value"
        placeholder="Select VPN Instance"
        show-clear
        :disabled="!selectedServerId"
        class="filter-select"
        @change="loadClients"
      />
    </div>

    <DataTable :value="clients" :loading="loading" striped-rows>
      <template #empty>No clients found.</template>
      <Column field="name" header="Name" />
      <Column header="Type">
        <template #body="{ data }">
          <Tag :value="data.client_type" :severity="data.client_type === 'user' ? 'info' : 'warn'" />
        </template>
      </Column>
      <Column header="Email">
        <template #body="{ data }">{{ data.email ?? '—' }}</template>
      </Column>
      <Column header="Certificate">
        <template #body="{ data }">
          <span v-if="data.cert_serial" class="cert-serial">{{ data.cert_serial.slice(0, 12) }}…</span>
          <span v-else class="text-muted">—</span>
        </template>
      </Column>
      <Column header="Status">
        <template #body="{ data }">
          <Tag :value="data.is_revoked ? 'Revoked' : 'Active'" :severity="data.is_revoked ? 'danger' : 'success'" />
        </template>
      </Column>
      <Column header="Actions" style="width: 12rem">
        <template #body="{ data }">
          <Button
            icon="pi pi-download"
            text
            rounded
            v-tooltip="'Download .ovpn'"
            :disabled="data.is_revoked"
            @click="downloadOvpn(data)"
          />
          <Button
            icon="pi pi-check-circle"
            text
            rounded
            severity="info"
            v-tooltip="'Verify PAM'"
            :disabled="data.client_type !== 'user'"
            @click="verifyPam(data)"
          />
          <Button
            icon="pi pi-ban"
            severity="warn"
            text
            rounded
            v-tooltip="'Revoke'"
            :disabled="data.is_revoked"
            @click="openRevokeDialog(data)"
          />
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            v-tooltip="'Delete'"
            @click="confirmDelete(data)"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Add Client Dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add Client" modal style="width: 480px">
      <div class="field field-inline" style="margin-bottom: 1rem">
        <Checkbox v-model="form.import_existing" :binary="true" input-id="import-existing" />
        <label for="import-existing" style="font-weight:600;cursor:pointer">Import existing PAM user</label>
      </div>

      <div class="field">
        <label>Name / Username *</label>
        <InputText v-model="form.name" class="w-full" placeholder="e.g. alice" />
        <small class="text-muted">{{ form.import_existing ? 'Must match an existing PAM username' : 'Used as the certificate CN and UNIX username' }}</small>
      </div>
      <div class="field">
        <label>Type *</label>
        <Select
          v-model="form.client_type"
          :options="clientTypeOptions"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <div class="field">
        <label>Email (optional)</label>
        <InputText v-model="form.email" class="w-full" placeholder="user@example.com" />
      </div>

      <template v-if="!form.import_existing">
        <Divider />
        <p class="section-label">Certificate Generation</p>

        <div class="field">
          <label>CA Passphrase</label>
          <InputText v-model="form.ca_passphrase" type="password" class="w-full" placeholder="Required to issue a certificate" />
          <small class="text-muted">Leave blank to create a client record without generating a certificate</small>
        </div>
        <div class="field">
          <label>Certificate Expire Days</label>
          <InputNumber v-model="form.cert_expire_days" class="w-full" :min="1" :max="9999" />
        </div>

        <template v-if="form.client_type === 'user'">
          <Divider />
          <p class="section-label">PAM User</p>
          <div class="field">
            <label>PAM Password *</label>
            <InputText v-model="form.pam_password" type="password" class="w-full" placeholder="Min 8 characters" />
          </div>
          <div class="field">
            <label>PAM Groups</label>
            <InputText v-model="pamGroupsStr" class="w-full" placeholder="openvpn" />
            <small class="text-muted">Comma-separated list</small>
          </div>
        </template>
      </template>

      <template v-else>
        <Divider />
        <p class="section-label" style="color:var(--p-blue-500)">
          The existing PAM user will be verified and any matching certificate in the PKI folder will be imported automatically.
        </p>
      </template>

      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addDialogVisible = false" />
        <Button :label="form.import_existing ? 'Import' : 'Create'" :loading="saving" @click="createClient" />
      </template>
    </Dialog>

    <!-- Revoke Dialog -->
    <Dialog v-model:visible="revokeDialogVisible" header="Revoke Client" modal style="width: 420px">
      <p>Revoke client <strong>{{ revokeTarget?.name }}</strong>?</p>
      <div class="field">
        <label>CA Passphrase (optional)</label>
        <InputText v-model="revokePassphrase" type="password" class="w-full" placeholder="Provide to also revoke the certificate in PKI" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="revokeDialogVisible = false" />
        <Button label="Revoke" severity="warn" :loading="revoking" @click="doRevoke" />
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
import Divider from 'primevue/divider'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import { useServersStore } from '@/stores/servers'
import { vpnInstancesApi } from '@/api/vpnInstances'
import { clientsApi } from '@/api/clients'
import type { VpnClientRead, VpnInstanceRead } from '@/types'

const toast = useToast()
const confirm = useConfirm()
const serversStore = useServersStore()

const clients = ref<VpnClientRead[]>([])
const instances = ref<VpnInstanceRead[]>([])
const loading = ref(false)
const selectedServerId = ref<number | null>(null)
const selectedInstanceId = ref<number | null>(null)
const addDialogVisible = ref(false)
const saving = ref(false)
const revokeDialogVisible = ref(false)
const revokeTarget = ref<VpnClientRead | null>(null)
const revokePassphrase = ref('')
const revoking = ref(false)
const pamGroupsStr = ref('openvpn')

const form = ref({
  name: '',
  client_type: 'user' as 'user' | 'site',
  email: '',
  ca_passphrase: '',
  cert_expire_days: 825,
  pam_password: '',
  import_existing: false,
})

const clientTypeOptions = [
  { label: 'User', value: 'user' },
  { label: 'Site-to-site', value: 'site' },
]

const serverOptions = computed(() =>
  serversStore.servers.map((s) => ({ label: s.name, value: s.id })),
)

const instanceOptions = computed(() =>
  instances.value.map((i) => ({ label: i.name, value: i.id })),
)

const selectedInstance = computed(() =>
  instances.value.find((i) => i.id === selectedInstanceId.value) ?? null,
)

async function onServerChange() {
  selectedInstanceId.value = null
  clients.value = []
  if (!selectedServerId.value) {
    instances.value = []
    return
  }
  try {
    instances.value = await vpnInstancesApi.list(selectedServerId.value)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load instances', life: 4000 })
  }
}

async function loadClients() {
  if (!selectedInstanceId.value) {
    clients.value = []
    return
  }
  loading.value = true
  try {
    clients.value = await clientsApi.list(selectedInstanceId.value)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load clients', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  form.value = { name: '', client_type: 'user', email: '', ca_passphrase: '', cert_expire_days: 825, pam_password: '', import_existing: false }
  pamGroupsStr.value = 'openvpn'
  addDialogVisible.value = true
}

async function createClient() {
  if (!selectedInstanceId.value || !form.value.name) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Name is required.', life: 3000 })
    return
  }
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      vpn_instance_id: selectedInstanceId.value,
      name: form.value.name,
      client_type: form.value.client_type,
      email: form.value.email || undefined,
      import_existing: form.value.import_existing,
    }
    if (!form.value.import_existing) {
      payload.cert_expire_days = form.value.cert_expire_days
      if (form.value.ca_passphrase) payload.ca_passphrase = form.value.ca_passphrase
      if (form.value.client_type === 'user') {
        payload.pam_password = form.value.pam_password
        payload.pam_groups = pamGroupsStr.value.split(',').map((g) => g.trim()).filter(Boolean)
      }
    }
    await clientsApi.create(payload as Parameters<typeof clientsApi.create>[0])
    toast.add({ severity: 'success', summary: 'Created', detail: 'Client created.', life: 3000 })
    addDialogVisible.value = false
    await loadClients()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to create client', life: 4000 })
  } finally {
    saving.value = false
  }
}

async function downloadOvpn(client: VpnClientRead) {
  try {
    await clientsApi.downloadOvpn(client.id, `${client.name}.ovpn`)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to download config', life: 4000 })
  }
}

async function verifyPam(client: VpnClientRead) {
  try {
    const result = await clientsApi.verifyPam(client.id)
    const detail = result.pam_verified
      ? `User "${result.username}" exists in group "${result.group}"`
      : `User "${result.username}" NOT found in group "${result.group}"`
    toast.add({ severity: result.pam_verified ? 'success' : 'warn', summary: 'PAM Check', detail, life: 5000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'PAM check failed', life: 4000 })
  }
}

function openRevokeDialog(client: VpnClientRead) {
  revokeTarget.value = client
  revokePassphrase.value = ''
  revokeDialogVisible.value = true
}

async function doRevoke() {
  if (!revokeTarget.value) return
  revoking.value = true
  try {
    await clientsApi.revoke(revokeTarget.value.id, revokePassphrase.value || undefined)
    toast.add({ severity: 'success', summary: 'Revoked', detail: 'Client revoked.', life: 3000 })
    revokeDialogVisible.value = false
    await loadClients()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to revoke', life: 4000 })
  } finally {
    revoking.value = false
  }
}

function confirmDelete(client: VpnClientRead) {
  confirm.require({
    message: `Delete client "${client.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await clientsApi.delete(client.id)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'Client deleted.', life: 3000 })
        await loadClients()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete', life: 4000 })
      }
    },
  })
}

onMounted(async () => {
  await serversStore.fetchServers()
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
.filter-bar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.filter-select {
  min-width: 220px;
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
.section-label {
  font-weight: 700;
  font-size: 0.875rem;
  text-transform: uppercase;
  color: var(--p-surface-500);
  margin: 0 0 0.75rem;
}
.w-full {
  width: 100%;
}
.text-muted {
  color: var(--p-surface-400);
}
.cert-serial {
  font-family: monospace;
  font-size: 0.8rem;
}
</style>
