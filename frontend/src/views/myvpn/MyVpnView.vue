<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">My VPN Configuration</h1>
        <p class="page-subtitle">Download your personal OpenVPN configuration file to connect to the VPN.</p>
      </div>
    </div>

    <div v-if="loading" class="loading-msg">
      <i class="pi pi-spin pi-spinner" /> Loading your configurations…
    </div>

    <div v-else-if="clients.length === 0" class="empty-state">
      <i class="pi pi-shield empty-icon" />
      <p>No VPN configurations have been issued for your account yet.</p>
      <p class="hint">Contact your administrator to have a certificate created for you.</p>
    </div>

    <div v-else class="client-grid">
      <div v-for="client in clients" :key="client.id" class="client-card">
        <div class="client-card-header">
          <i class="pi pi-shield card-icon" />
          <div class="client-info">
            <div class="client-name">{{ client.name }}</div>
            <div class="client-meta">{{ instanceName(client.vpn_instance_id) }}</div>
          </div>
          <Tag v-if="client.is_revoked" value="Revoked" severity="danger" />
        </div>

        <div class="client-details">
          <div class="detail-row">
            <span class="detail-label">Type</span>
            <span>{{ client.client_type }}</span>
          </div>
          <div v-if="client.cert_serial" class="detail-row">
            <span class="detail-label">Certificate</span>
            <span class="mono">{{ client.cert_serial.slice(0, 16) }}…</span>
          </div>
        </div>

        <div class="client-actions">
          <Button
            label="Download .ovpn"
            icon="pi pi-download"
            :disabled="client.is_revoked"
            :loading="downloadingId === client.id"
            @click="downloadOvpn(client)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { clientsApi } from '@/api/clients'
import { vpnInstancesApi } from '@/api/vpnInstances'
import type { VpnClientRead, VpnInstanceRead } from '@/types'

const toast = useToast()

const clients = ref<VpnClientRead[]>([])
const instances = ref<VpnInstanceRead[]>([])
const loading = ref(false)
const downloadingId = ref<number | null>(null)

function instanceName(id: number): string {
  return instances.value.find((i) => i.id === id)?.name ?? `Instance #${id}`
}

async function loadData() {
  loading.value = true
  try {
    const [cls, insts] = await Promise.all([
      clientsApi.list(),
      vpnInstancesApi.list(),
    ])
    clients.value = cls
    instances.value = insts
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load data', life: 4000 })
  } finally {
    loading.value = false
  }
}

async function downloadOvpn(client: VpnClientRead) {
  downloadingId.value = client.id
  try {
    await clientsApi.downloadOvpn(client.id, `${client.name}.ovpn`)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to download config', life: 4000 })
  } finally {
    downloadingId.value = null
  }
}

onMounted(loadData)
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}
.page-title {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
  font-weight: 700;
}
.page-subtitle {
  margin: 0;
  font-size: 0.875rem;
  color: var(--p-surface-500);
}
.loading-msg {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--p-surface-400);
  padding: 2rem;
}
.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--p-surface-400);
}
.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  display: block;
}
.hint {
  font-size: 0.875rem;
  color: var(--p-surface-400);
}
.client-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.25rem;
}
.client-card {
  background: var(--p-surface-0);
  border: 1px solid var(--p-surface-200);
  border-radius: 8px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.client-card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}
.card-icon {
  font-size: 1.5rem;
  color: var(--p-primary-color);
  margin-top: 0.1rem;
}
.client-info {
  flex: 1;
}
.client-name {
  font-weight: 700;
  font-size: 1rem;
}
.client-meta {
  font-size: 0.8rem;
  color: var(--p-surface-400);
  margin-top: 0.1rem;
}
.client-details {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  background: var(--p-surface-50);
  border-radius: 6px;
  padding: 0.6rem 0.75rem;
}
.detail-row {
  display: flex;
  gap: 1rem;
  font-size: 0.85rem;
}
.detail-label {
  font-weight: 600;
  min-width: 80px;
  color: var(--p-surface-500);
}
.mono {
  font-family: monospace;
  font-size: 0.8rem;
}
.client-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
