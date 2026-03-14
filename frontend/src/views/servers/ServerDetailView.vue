<template>
  <div v-if="server">
    <div class="page-header">
      <h1 class="page-title">{{ server.name }}</h1>
      <div class="header-actions">
        <Button
          label="Test Connection"
          icon="pi pi-wifi"
          :loading="testingConn"
          @click="testConnection"
          severity="secondary"
        />
        <Button
          label="Discover Configs"
          icon="pi pi-search"
          :loading="discovering"
          @click="discoverConfigs"
          severity="secondary"
        />
      </div>
    </div>

    <div class="detail-grid">
      <Card>
        <template #title>Details</template>
        <template #content>
          <dl class="detail-list">
            <dt>Type</dt><dd>{{ server.is_local ? 'Local' : 'Remote' }}</dd>
            <dt>Host</dt><dd>{{ server.is_local ? 'localhost' : server.host }}</dd>
            <dt>Port</dt><dd>{{ server.port }}</dd>
            <dt>SSH User</dt><dd>{{ server.ssh_username ?? '—' }}</dd>
            <dt>Fingerprint</dt>
            <dd>
              <code v-if="server.ssh_host_fingerprint" class="fingerprint">{{ server.ssh_host_fingerprint }}</code>
              <Tag v-else value="Not verified" severity="warn" />
            </dd>
          </dl>
        </template>
      </Card>

      <Card v-if="connTestResult">
        <template #title>Connection Test</template>
        <template #content>
          <Tag
            :value="connTestResult.success ? 'Success' : 'Failed'"
            :severity="connTestResult.success ? 'success' : 'danger'"
          />
          <p class="mt-2">{{ connTestResult.message }}</p>
          <p v-if="connTestResult.fingerprint">
            <strong>Fingerprint:</strong> <code>{{ connTestResult.fingerprint }}</code>
          </p>
        </template>
      </Card>
    </div>

    <Card v-if="discoveredConfigs.length > 0" class="mt-4">
      <template #title>Discovered VPN Configs</template>
      <template #content>
        <DataTable :value="discoveredConfigs" size="small">
          <Column field="name" header="Name" />
          <Column field="path" header="Path" />
          <Column header="Size">
            <template #body="{ data }">{{ (data.size_bytes / 1024).toFixed(1) }} KB</template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
  <div v-else class="loading">
    <ProgressSpinner />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ProgressSpinner from 'primevue/progressspinner'
import { useToast } from 'primevue/usetoast'
import { serversApi } from '@/api/servers'
import type { ServerRead, ServerTestConnectionResult, DiscoveredConfig } from '@/types'

const route = useRoute()
const toast = useToast()

const server = ref<ServerRead | null>(null)
const connTestResult = ref<ServerTestConnectionResult | null>(null)
const discoveredConfigs = ref<DiscoveredConfig[]>([])
const testingConn = ref(false)
const discovering = ref(false)

onMounted(async () => {
  server.value = await serversApi.get(Number(route.params.id))
})

async function testConnection(): Promise<void> {
  testingConn.value = true
  try {
    connTestResult.value = await serversApi.testConnection(Number(route.params.id))
    if (connTestResult.value.success && server.value) {
      server.value.ssh_host_fingerprint = connTestResult.value.fingerprint
    }
  } catch (e: unknown) {
    toast.add({ severity: 'error', summary: 'Test Failed', detail: (e as { detail?: string }).detail, life: 5000 })
  } finally {
    testingConn.value = false
  }
}

async function discoverConfigs(): Promise<void> {
  discovering.value = true
  try {
    discoveredConfigs.value = await serversApi.discover(Number(route.params.id))
    toast.add({ severity: 'info', summary: 'Discovered', detail: `Found ${discoveredConfigs.value.length} config(s)`, life: 3000 })
  } catch (e: unknown) {
    toast.add({ severity: 'error', summary: 'Discovery Failed', detail: (e as { detail?: string }).detail, life: 5000 })
  } finally {
    discovering.value = false
  }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.page-title { margin: 0; font-size: 1.5rem; font-weight: 700; }
.header-actions { display: flex; gap: 0.75rem; }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }
.detail-list { display: grid; grid-template-columns: 120px 1fr; gap: 0.5rem; }
.detail-list dt { font-weight: 600; color: var(--p-surface-600); }
.fingerprint { font-size: 0.75rem; word-break: break-all; }
.mt-2 { margin-top: 0.5rem; }
.mt-4 { margin-top: 1.5rem; }
.loading { display: flex; justify-content: center; padding: 4rem; }
</style>
