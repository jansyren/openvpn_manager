<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Backup & Restore</h1>
      <Button v-if="authStore.canAdminister" label="Create Backup" icon="pi pi-plus" @click="openCreateDialog" />
    </div>

    <DataTable :value="backups" :loading="loading" striped-rows show-gridlines>
      <Column field="filename" header="Filename" />
      <Column header="Type">
        <template #body="{ data }">
          <Tag :value="data.backup_type" />
        </template>
      </Column>
      <Column header="Size">
        <template #body="{ data }">
          {{ data.size_bytes ? (data.size_bytes / 1024 / 1024).toFixed(2) + ' MB' : '—' }}
        </template>
      </Column>
      <Column field="created_at" header="Created">
        <template #body="{ data }">{{ new Date(data.created_at).toLocaleString() }}</template>
      </Column>
      <Column field="notes" header="Notes">
        <template #body="{ data }">{{ data.notes || '—' }}</template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
          <div class="action-btns">
            <Button icon="pi pi-download" size="small" severity="secondary" text @click="downloadBackup(data)" />
            <Button v-if="authStore.canAdminister" icon="pi pi-history" size="small" severity="warn" text @click="openRestoreDialog(data)" />
            <Button v-if="authStore.canAdminister" icon="pi pi-trash" size="small" severity="danger" text @click="confirmDelete(data)" />
          </div>
        </template>
      </Column>
    </DataTable>

    <!-- Create Backup Dialog -->
    <Dialog v-model:visible="showCreateDialog" header="Create Backup" modal style="width: 440px">
      <div class="field">
        <label>Server</label>
        <Select v-model="createForm.server_id" :options="serverOptions" option-label="label" option-value="value" class="w-full" placeholder="Select server" @change="onCreateServerChange" />
      </div>
      <div class="field">
        <label>Backup Type</label>
        <Select
          v-model="createForm.backup_type"
          :options="backupTypes"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <div v-if="createForm.backup_type !== 'server_config'" class="field">
        <label>VPN Instance <small class="text-muted">(selects the correct PKI directory)</small></label>
        <Select
          v-model="createForm.vpn_instance_id"
          :options="[{ label: '— Use default path —', value: null }, ...createInstanceOptions]"
          option-label="label"
          option-value="value"
          class="w-full"
          :disabled="!createForm.server_id"
          placeholder="Select instance"
        />
      </div>
      <div class="field">
        <label>Notes</label>
        <Textarea v-model="createForm.notes" class="w-full" rows="2" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showCreateDialog = false" />
        <Button label="Create" icon="pi pi-check" :loading="creating" @click="createBackup" />
      </template>
    </Dialog>

    <!-- Restore Confirmation Dialog -->
    <Dialog v-model:visible="showRestoreDialog" header="Confirm Restore" modal style="width: 480px">
      <Message severity="warn" :closable="false">
        This will overwrite existing files on the server. A pre-restore snapshot will be created automatically.
      </Message>
      <p class="mt-2">
        To confirm, enter the SHA-256 checksum of the backup file:
        <code class="sha256">{{ selectedBackup?.sha256 }}</code>
      </p>
      <div class="field mt-2">
        <InputText v-model="restoreConfirmSha256" class="w-full" placeholder="Enter SHA-256 to confirm" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="showRestoreDialog = false" />
        <Button
          label="Restore"
          icon="pi pi-history"
          severity="danger"
          :disabled="restoreConfirmSha256 !== selectedBackup?.sha256"
          :loading="restoring"
          @click="restoreBackup"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import apiClient from '@/api/client'
import { useServersStore } from '@/stores/servers'
import { useAuthStore } from '@/stores/auth'
import { vpnInstancesApi } from '@/api/vpnInstances'
import type { BackupRead, VpnInstanceRead } from '@/types'

const toast = useToast()
const confirm = useConfirm()
const serversStore = useServersStore()
const authStore = useAuthStore()

const backups = ref<BackupRead[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const showRestoreDialog = ref(false)
const selectedBackup = ref<BackupRead | null>(null)
const restoreConfirmSha256 = ref('')
const creating = ref(false)
const restoring = ref(false)
const createInstances = ref<VpnInstanceRead[]>([])

const createForm = ref({ server_id: null as number | null, backup_type: 'full', notes: '', vpn_instance_id: null as number | null })

const serverOptions = computed(() =>
  serversStore.servers.map((s) => ({ label: s.name, value: s.id }))
)

const createInstanceOptions = computed(() =>
  createInstances.value.map((i) => ({ label: i.name, value: i.id }))
)

async function onCreateServerChange() {
  createForm.value.vpn_instance_id = null
  createInstances.value = []
  if (createForm.value.server_id) {
    try {
      createInstances.value = await vpnInstancesApi.list(createForm.value.server_id)
    } catch (_) {
      // ignore
    }
  }
}

const backupTypes = [
  { label: 'Full (openvpn + easy-rsa)', value: 'full' },
  { label: 'Server Config only', value: 'server_config' },
  { label: 'Easy-RSA PKI only', value: 'easyrsa' },
]

onMounted(async () => {
  await serversStore.fetchAll()
  await fetchBackups()
})

async function fetchBackups(): Promise<void> {
  loading.value = true
  try {
    const resp = await apiClient.get<BackupRead[]>('/backup')
    backups.value = resp.data
  } finally {
    loading.value = false
  }
}

function openCreateDialog(): void {
  createForm.value = { server_id: null, backup_type: 'full', notes: '', vpn_instance_id: null }
  createInstances.value = []
  showCreateDialog.value = true
}

async function createBackup(): Promise<void> {
  creating.value = true
  try {
    const payload: Record<string, unknown> = {
      server_id: createForm.value.server_id,
      backup_type: createForm.value.backup_type,
      notes: createForm.value.notes || null,
    }
    if (createForm.value.vpn_instance_id) payload.vpn_instance_id = createForm.value.vpn_instance_id
    await apiClient.post('/backup', payload)
    toast.add({ severity: 'success', summary: 'Created', detail: 'Backup created', life: 3000 })
    showCreateDialog.value = false
    await fetchBackups()
  } catch (e: unknown) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail, life: 5000 })
  } finally {
    creating.value = false
  }
}

function downloadBackup(backup: BackupRead): void {
  window.open(`/api/v1/backup/${backup.id}/download`, '_blank')
}

function openRestoreDialog(backup: BackupRead): void {
  selectedBackup.value = backup
  restoreConfirmSha256.value = ''
  showRestoreDialog.value = true
}

async function restoreBackup(): Promise<void> {
  if (!selectedBackup.value) return
  restoring.value = true
  try {
    await apiClient.post(`/backup/${selectedBackup.value.id}/restore`, {
      backup_id: selectedBackup.value.id,
      expected_sha256: restoreConfirmSha256.value,
    })
    toast.add({ severity: 'success', summary: 'Restored', detail: 'Backup restored successfully', life: 3000 })
    showRestoreDialog.value = false
  } catch (e: unknown) {
    toast.add({ severity: 'error', summary: 'Restore Failed', detail: (e as { detail?: string }).detail, life: 5000 })
  } finally {
    restoring.value = false
  }
}

function confirmDelete(backup: BackupRead): void {
  confirm.require({
    message: `Delete backup "${backup.filename}"? This cannot be undone.`,
    header: 'Confirm Deletion',
    severity: 'danger',
    accept: async () => {
      await apiClient.delete(`/backup/${backup.id}`)
      await fetchBackups()
      toast.add({ severity: 'success', summary: 'Deleted', detail: 'Backup deleted', life: 3000 })
    },
  })
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.page-title { margin: 0; font-size: 1.5rem; font-weight: 700; }
.action-btns { display: flex; gap: 0.25rem; }
.field { margin-bottom: 1rem; }
.field label { display: block; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.375rem; }
.sha256 { display: block; font-size: 0.7rem; word-break: break-all; margin-top: 0.25rem; }
.mt-2 { margin-top: 0.75rem; }
.text-muted { color: var(--p-surface-400); font-size: 0.8rem; }
</style>
