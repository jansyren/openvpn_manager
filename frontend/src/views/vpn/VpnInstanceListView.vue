<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">VPN Instances</h1>
      <div class="action-btns">
        <Button label="Discover" icon="pi pi-search" severity="secondary" :disabled="!selectedServerId" :loading="discovering" @click="discoverConfigs" />
        <Button label="Add Instance" icon="pi pi-plus" @click="openAddDialog" />
      </div>
    </div>

    <div class="filter-bar">
      <Select
        v-model="selectedServerId"
        :options="serverOptions"
        option-label="label"
        option-value="value"
        placeholder="All Servers"
        show-clear
        class="filter-select"
        @change="loadInstances"
      />
    </div>

    <DataTable :value="instances" :loading="loading" striped-rows>
      <template #empty>No VPN instances found.</template>
      <Column field="name" header="Name">
        <template #body="{ data }">
          <a class="instance-link" @click="goToDetail(data)">{{ data.name }}</a>
        </template>
      </Column>
      <Column header="Server">
        <template #body="{ data }">
          {{ serverName(data.server_id) }}
        </template>
      </Column>
      <Column field="proto" header="Proto" />
      <Column field="port" header="Port" />
      <Column field="dev" header="Dev" />
      <Column field="status" header="Status">
        <template #body="{ data }">
          <Tag :value="data.status" :severity="statusSeverity(data.status)" />
        </template>
      </Column>
      <Column header="Actions" style="width: 8rem">
        <template #body="{ data }">
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
            @click="confirmDelete(data)"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Edit Instance Dialog -->
    <Dialog v-model:visible="editDialogVisible" header="Edit VPN Instance" modal style="width: 500px">
      <div class="field">
        <label>Name *</label>
        <InputText v-model="editForm.name" class="w-full" />
      </div>
      <div class="field">
        <label>Protocol</label>
        <Select
          v-model="editForm.proto"
          :options="protoOptions"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <div class="field">
        <label>Port</label>
        <InputNumber v-model="editForm.port" class="w-full" :min="1" :max="65535" />
      </div>
      <div class="field">
        <label>Dev</label>
        <InputText v-model="editForm.dev" class="w-full" />
      </div>
      <div class="field">
        <label>Network</label>
        <InputText v-model="editForm.network" class="w-full" placeholder="10.8.0.0" />
      </div>
      <div class="field">
        <label>Netmask</label>
        <InputText v-model="editForm.netmask" class="w-full" placeholder="255.255.255.0" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editDialogVisible = false" />
        <Button label="Save" :loading="editSaving" @click="saveEdit" />
      </template>
    </Dialog>

    <!-- Add Instance Dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add VPN Instance" modal style="width: 500px">
      <div class="field">
        <label>Server *</label>
        <Select
          v-model="form.server_id"
          :options="serverOptions"
          option-label="label"
          option-value="value"
          placeholder="Select server"
          class="w-full"
        />
      </div>
      <div class="field">
        <label>Name *</label>
        <InputText v-model="form.name" class="w-full" placeholder="e.g. vpn0" />
      </div>
      <div class="field">
        <label>Config Path *</label>
        <InputText v-model="form.config_path" class="w-full" placeholder="/etc/openvpn/server.conf" />
      </div>
      <div class="field">
        <label>Protocol</label>
        <Select
          v-model="form.proto"
          :options="protoOptions"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <div class="field">
        <label>Port</label>
        <InputNumber v-model="form.port" class="w-full" :min="1" :max="65535" />
      </div>
      <div class="field">
        <label>Dev</label>
        <InputText v-model="form.dev" class="w-full" placeholder="tun0" />
      </div>
      <div class="field">
        <label>Network</label>
        <InputText v-model="form.network" class="w-full" placeholder="10.8.0.0" />
      </div>
      <div class="field">
        <label>Netmask</label>
        <InputText v-model="form.netmask" class="w-full" placeholder="255.255.255.0" />
      </div>
      <div class="field">
        <label>EasyRSA Path (optional)</label>
        <InputText v-model="form.easyrsa_path" class="w-full" placeholder="/etc/easyrsa" />
      </div>
      <div class="field">
        <label>EasyRSA Server (optional — for offline CA)</label>
        <Select
          v-model="form.easyrsa_server_id"
          :options="[{ label: '— Same as VPN server —', value: null }, ...serverOptions]"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addDialogVisible = false" />
        <Button label="Create" :loading="saving" @click="createInstance" />
      </template>
    </Dialog>
    <!-- Discover Dialog -->
    <Dialog v-model:visible="discoverDialogVisible" header="Discovered Configs" modal style="width: 560px">
      <p v-if="discoveredConfigs.length === 0" class="empty-msg">No .conf files found on this server.</p>
      <div v-for="cfg in discoveredConfigs" :key="cfg.path" class="discover-row">
        <div class="discover-info">
          <span class="discover-path">{{ cfg.path }}</span>
          <span class="discover-meta">{{ cfg.name }} · {{ formatBytes(cfg.size_bytes) }}</span>
        </div>
        <Button label="Import" icon="pi pi-plus" size="small" @click="importConfig(cfg)" />
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" @click="discoverDialogVisible = false" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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
import { useServersStore } from '@/stores/servers'
import { serversApi } from '@/api/servers'
import { vpnInstancesApi } from '@/api/vpnInstances'
import type { VpnInstanceRead, DiscoveredConfig } from '@/types'

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const serversStore = useServersStore()

const instances = ref<VpnInstanceRead[]>([])
const loading = ref(false)
const selectedServerId = ref<number | null>(null)
const addDialogVisible = ref(false)
const saving = ref(false)
const discovering = ref(false)
const discoverDialogVisible = ref(false)
const discoveredConfigs = ref<DiscoveredConfig[]>([])
const editDialogVisible = ref(false)
const editSaving = ref(false)
const editTarget = ref<VpnInstanceRead | null>(null)
const editForm = ref({ name: '', proto: 'udp' as 'udp' | 'tcp', port: 1194, dev: 'tun0', network: '', netmask: '' })

const form = ref({
  server_id: null as number | null,
  name: '',
  config_path: '',
  proto: 'udp' as 'udp' | 'tcp',
  port: 1194,
  dev: 'tun0',
  network: '10.8.0.0',
  netmask: '255.255.255.0',
  easyrsa_path: '',
  easyrsa_server_id: null as number | null,
})

const protoOptions = [
  { label: 'UDP', value: 'udp' },
  { label: 'TCP', value: 'tcp' },
]

const serverOptions = computed(() =>
  serversStore.servers.map((s) => ({ label: s.name, value: s.id })),
)

function serverName(serverId: number): string {
  return serversStore.servers.find((s) => s.id === serverId)?.name ?? String(serverId)
}

function statusSeverity(status: string): string {
  if (status === 'active') return 'success'
  if (status === 'inactive') return 'secondary'
  return 'warn'
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB`
}

async function loadInstances() {
  loading.value = true
  try {
    instances.value = await vpnInstancesApi.list(selectedServerId.value ?? undefined)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load instances', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  form.value = { server_id: selectedServerId.value, name: '', config_path: '', proto: 'udp', port: 1194, dev: 'tun0', network: '10.8.0.0', netmask: '255.255.255.0', easyrsa_path: '', easyrsa_server_id: null }
  addDialogVisible.value = true
}

async function discoverConfigs() {
  if (!selectedServerId.value) return
  discovering.value = true
  try {
    discoveredConfigs.value = await serversApi.discover(selectedServerId.value)
    discoverDialogVisible.value = true
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to discover configs', life: 4000 })
  } finally {
    discovering.value = false
  }
}

function importConfig(cfg: DiscoveredConfig) {
  discoverDialogVisible.value = false
  const name = cfg.name.replace(/\.conf$/, '').replace(/[^a-zA-Z0-9_-]/g, '-')
  form.value = { server_id: selectedServerId.value, name, config_path: cfg.path, proto: 'udp', port: 1194, dev: 'tun0', network: '10.8.0.0', netmask: '255.255.255.0', easyrsa_path: '', easyrsa_server_id: null }
  addDialogVisible.value = true
}

async function createInstance() {
  if (!form.value.server_id || !form.value.name || !form.value.config_path) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Server, name and config path are required.', life: 3000 })
    return
  }
  saving.value = true
  try {
    await vpnInstancesApi.create({
      server_id: form.value.server_id,
      name: form.value.name,
      config_path: form.value.config_path,
      proto: form.value.proto,
      port: form.value.port,
      dev: form.value.dev,
      network: form.value.network || undefined,
      netmask: form.value.netmask || undefined,
      easyrsa_path: form.value.easyrsa_path || undefined,
      easyrsa_server_id: form.value.easyrsa_server_id ?? undefined,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: 'VPN instance created.', life: 3000 })
    addDialogVisible.value = false
    await loadInstances()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to create instance', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(instance: VpnInstanceRead) {
  confirm.require({
    message: `Delete VPN instance "${instance.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await vpnInstancesApi.delete(instance.id)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'Instance deleted.', life: 3000 })
        await loadInstances()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete', life: 4000 })
      }
    },
  })
}

function openEditDialog(data: VpnInstanceRead) {
  editTarget.value = data
  editForm.value = {
    name: data.name,
    proto: data.proto as 'udp' | 'tcp',
    port: data.port,
    dev: data.dev,
    network: data.network ?? '',
    netmask: data.netmask ?? '',
  }
  editDialogVisible.value = true
}

async function saveEdit() {
  if (!editTarget.value) return
  editSaving.value = true
  try {
    await vpnInstancesApi.update(editTarget.value.id, {
      name: editForm.value.name,
      proto: editForm.value.proto,
      port: editForm.value.port,
      dev: editForm.value.dev,
      network: editForm.value.network || null,
      netmask: editForm.value.netmask || null,
    })
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Instance updated.', life: 3000 })
    editDialogVisible.value = false
    await loadInstances()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update', life: 4000 })
  } finally {
    editSaving.value = false
  }
}

function goToDetail(data: VpnInstanceRead) {
  router.push({ name: 'vpn-instance-detail', params: { id: data.id } })
}

onMounted(async () => {
  await serversStore.fetchServers()
  await loadInstances()
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
  margin-bottom: 1rem;
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
.w-full {
  width: 100%;
}
.instance-link {
  color: var(--p-primary-color);
  cursor: pointer;
  text-decoration: underline;
}
.discover-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--p-surface-200);
}
.discover-row:last-child {
  border-bottom: none;
}
.discover-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}
.discover-path {
  font-weight: 600;
  font-size: 0.875rem;
  word-break: break-all;
}
.discover-meta {
  font-size: 0.75rem;
  color: var(--p-surface-500);
}
.empty-msg {
  color: var(--p-surface-500);
  padding: 0.5rem 0;
}
</style>
