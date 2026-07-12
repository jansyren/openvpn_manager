<template>
  <div>
    <PageHeader title="Route Manager">
      <Button
        label="Show Live Routing Table"
        icon="pi pi-table"
        severity="secondary"
        :loading="liveLoading"
        :disabled="!ctx.selectedServerId"
        @click="loadLiveRoutes"
      />
      <Button label="Add Route" icon="pi pi-plus" @click="openAddDialog" />
    </PageHeader>

    <Message v-if="!ctx.selectedServerId" severity="info" :closable="false" style="margin-bottom:1rem">
      Select a server in the header bar to view routes.
    </Message>

    <Panel v-if="liveRoutes !== null" header="Live Routing Table" toggleable class="live-panel">
      <pre class="live-output">{{ liveRoutes.routes.join('\n') || 'Empty routing table.' }}</pre>
    </Panel>

    <DataTable :value="routes" :loading="loading" striped-rows>
      <template #empty>No routes found.</template>
      <Column header="Server">
        <template #body="{ data }">{{ serverName(data.server_id) }}</template>
      </Column>
      <Column field="source_tun" header="Source TUN" />
      <Column field="dest_tun" header="Dest TUN" />
      <Column field="destination_network" header="Destination Network" />
      <Column field="metric" header="Metric" />
      <Column header="Persistent">
        <template #body="{ data }">
          <Tag :value="data.is_persistent ? 'Yes' : 'No'" :severity="data.is_persistent ? 'success' : 'secondary'" />
        </template>
      </Column>
      <Column header="Active">
        <template #body="{ data }">
          <Tag :value="data.is_active ? 'Active' : 'Inactive'" :severity="data.is_active ? 'success' : 'secondary'" />
        </template>
      </Column>
      <Column header="Actions" style="width: 10rem">
        <template #body="{ data }">
          <Button
            v-if="!data.is_active"
            icon="pi pi-play"
            severity="success"
            text
            rounded
            v-tooltip="'Apply route'"
            :loading="applyingId === data.id"
            @click="applyRoute(data)"
          />
          <Button
            v-else
            icon="pi pi-stop"
            severity="warn"
            text
            rounded
            v-tooltip="'Remove route'"
            :loading="applyingId === data.id"
            @click="removeRoute(data)"
          />
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            @click="confirmDelete(data)"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Add Route Dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add Route" modal style="width: 480px">
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
        <label>Source TUN *</label>
        <InputText v-model="form.source_tun" class="w-full" placeholder="tun0" />
      </div>
      <div class="field">
        <label>Dest TUN *</label>
        <InputText v-model="form.dest_tun" class="w-full" placeholder="tun1" />
      </div>
      <div class="field">
        <label>Destination Network *</label>
        <InputText v-model="form.destination_network" class="w-full" placeholder="10.8.0.0/24" />
      </div>
      <div class="field">
        <label>Metric</label>
        <InputNumber v-model="form.metric" class="w-full" :min="0" />
      </div>
      <div class="field field-inline">
        <Checkbox v-model="form.is_persistent" :binary="true" input-id="persistent" />
        <label for="persistent">Persistent</label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addDialogVisible = false" />
        <Button label="Create" :loading="saving" @click="createRoute" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
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
import Panel from 'primevue/panel'
import Message from 'primevue/message'
import PageHeader from '@/components/PageHeader.vue'
import { useApiToast } from '@/composables/useApiToast'
import { useContextStore } from '@/stores/context'
import { routesApi } from '@/api/routes'
import type { RouteRead, LiveRoutingTable } from '@/types'

const { toast, error } = useApiToast()
const confirm = useConfirm()
const ctx = useContextStore()

const routes = ref<RouteRead[]>([])
const loading = ref(false)
const liveRoutes = ref<LiveRoutingTable | null>(null)
const liveLoading = ref(false)
const addDialogVisible = ref(false)
const saving = ref(false)
const applyingId = ref<number | null>(null)

const form = ref({
  server_id: null as number | null,
  source_tun: '',
  dest_tun: '',
  destination_network: '',
  metric: 0,
  is_persistent: false,
})

const serverOptions = computed(() =>
  ctx.servers.map((s) => ({ label: s.name, value: s.id })),
)

function serverName(serverId: number): string {
  return ctx.servers.find((s) => s.id === serverId)?.name ?? String(serverId)
}

watch(
  () => ctx.selectedServerId,
  async () => {
    liveRoutes.value = null
    await loadRoutes()
  },
)

async function loadRoutes() {
  loading.value = true
  try {
    routes.value = await routesApi.list(ctx.selectedServerId ?? undefined)
  } catch (e) {
    error(e, 'Failed to load routes')
  } finally {
    loading.value = false
  }
}

async function loadLiveRoutes() {
  if (!ctx.selectedServerId) return
  liveLoading.value = true
  try {
    liveRoutes.value = await routesApi.getLive(ctx.selectedServerId)
  } catch (e) {
    error(e, 'Failed to load live routes')
  } finally {
    liveLoading.value = false
  }
}

function openAddDialog() {
  form.value = {
    server_id: ctx.selectedServerId,
    source_tun: '',
    dest_tun: '',
    destination_network: '',
    metric: 0,
    is_persistent: false,
  }
  addDialogVisible.value = true
}

async function createRoute() {
  if (!form.value.server_id || !form.value.source_tun || !form.value.dest_tun || !form.value.destination_network) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Server, source TUN, dest TUN and destination network are required.', life: 3000 })
    return
  }
  saving.value = true
  try {
    await routesApi.create({
      server_id: form.value.server_id,
      source_tun: form.value.source_tun,
      dest_tun: form.value.dest_tun,
      destination_network: form.value.destination_network,
      metric: form.value.metric,
      is_persistent: form.value.is_persistent,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: 'Route created.', life: 3000 })
    addDialogVisible.value = false
    await loadRoutes()
  } catch (e) {
    error(e, 'Failed to create route')
  } finally {
    saving.value = false
  }
}

async function applyRoute(route: RouteRead) {
  applyingId.value = route.id
  try {
    await routesApi.apply(route.id)
    toast.add({ severity: 'success', summary: 'Applied', detail: 'Route applied.', life: 3000 })
    await loadRoutes()
  } catch (e) {
    error(e, 'Failed to apply route')
  } finally {
    applyingId.value = null
  }
}

async function removeRoute(route: RouteRead) {
  applyingId.value = route.id
  try {
    await routesApi.remove(route.id)
    toast.add({ severity: 'success', summary: 'Removed', detail: 'Route deactivated.', life: 3000 })
    await loadRoutes()
  } catch (e) {
    error(e, 'Failed to remove route')
  } finally {
    applyingId.value = null
  }
}

function confirmDelete(route: RouteRead) {
  confirm.require({
    message: `Delete route to "${route.destination_network}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await routesApi.delete(route.id)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'Route deleted.', life: 3000 })
        await loadRoutes()
      } catch (e) {
        error(e, 'Failed to delete')
      }
    },
  })
}

onMounted(async () => {
  await loadRoutes()
})
</script>

<style scoped>
.live-panel {
  margin-bottom: 1.5rem;
}
.live-output {
  background: var(--p-surface-900);
  color: var(--p-surface-100);
  padding: 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
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
</style>
