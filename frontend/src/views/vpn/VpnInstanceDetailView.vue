<template>
  <div>
    <div class="page-header">
      <div class="header-left">
        <Button icon="pi pi-arrow-left" text rounded @click="router.back()" />
        <div>
          <h1 class="page-title">{{ instance?.name ?? 'Loading…' }}</h1>
          <p class="page-subtitle">{{ instance?.config_path }}</p>
        </div>
      </div>
    </div>

    <div v-if="instance" class="status-card">
      <div class="stat-grid">
        <div class="stat-item"><span class="stat-label">Protocol</span><span>{{ instance.proto }}</span></div>
        <div class="stat-item"><span class="stat-label">Port</span><span>{{ instance.port }}</span></div>
        <div class="stat-item"><span class="stat-label">Dev</span><span>{{ instance.dev }}</span></div>
        <div class="stat-item"><span class="stat-label">Network</span><span>{{ instance.network ?? '—' }}</span></div>
        <div class="stat-item"><span class="stat-label">PAM</span><span>{{ instance.pam_enabled ? 'Enabled' : 'Disabled' }}</span></div>
        <div class="stat-item">
          <span class="stat-label">Status</span>
          <Tag :value="instance.status" :severity="statusSeverity(instance.status)" />
        </div>
      </div>
    </div>

    <TabView v-if="instance">
      <!-- Logs Tab -->
      <TabPanel header="Logs">
        <div class="tab-toolbar">
          <Select
            v-model="logLines"
            :options="logLineOptions"
            option-label="label"
            option-value="value"
            style="width: 120px"
          />
          <Button label="Refresh" icon="pi pi-refresh" :loading="logsLoading" @click="loadLogs" />
        </div>
        <pre class="log-output">{{ logs || 'No logs available.' }}</pre>
      </TabPanel>

      <!-- Config Tab -->
      <TabPanel header="Config">
        <div class="tab-toolbar">
          <Button label="Refresh" icon="pi pi-refresh" :loading="configLoading" @click="loadConfig" />
        </div>
        <div v-if="configDirectives" class="directive-list">
          <div
            v-for="(value, key) in configDirectives"
            :key="key"
            class="directive-row"
          >
            <span class="directive-key">{{ key }}</span>
            <span class="directive-value">{{ formatDirectiveValue(value) }}</span>
          </div>
          <p v-if="Object.keys(configDirectives).length === 0" class="empty-msg">No directives found.</p>
        </div>
      </TabPanel>

      <!-- Settings Tab -->
      <TabPanel header="Settings">
        <div class="settings-section">
          <h3 class="settings-heading">Client Config</h3>

          <div class="field field-inline">
            <Checkbox v-model="settingsPamEnabled" :binary="true" input-id="pam-enabled" @change="saveSettings" />
            <label for="pam-enabled">Require PAM login (<code>auth-user-pass</code> in client configs)</label>
          </div>

          <div class="field" style="margin-top: 1.25rem">
            <label for="tls-auth-key">TLS Auth Key (ta.key) — paste contents for <code>tls-auth</code> inline block</label>
            <Textarea
              id="tls-auth-key"
              v-model="settingsTlsAuthKey"
              rows="10"
              class="w-full"
              style="font-family: monospace; font-size: 0.8rem"
              placeholder="-----BEGIN OpenVPN Static key V1-----&#10;...&#10;-----END OpenVPN Static key V1-----"
            />
            <small class="text-muted">Leave blank to omit tls-auth from generated client configs.</small>
          </div>
          <Button label="Save Settings" icon="pi pi-save" :loading="settingsSaving" @click="saveSettings" />
        </div>
      </TabPanel>

      <!-- Service Tab -->
      <TabPanel header="Service">
        <div class="service-actions">
          <Button
            v-for="action in serviceActions"
            :key="action.name"
            :label="action.label"
            :icon="action.icon"
            :severity="action.severity"
            :loading="actionLoading === action.name"
            @click="runAction(action.name)"
          />
        </div>
        <div v-if="serviceStatus" class="service-status-card">
          <div class="stat-grid">
            <div class="stat-item"><span class="stat-label">Status</span><Tag :value="serviceStatus.status" :severity="statusSeverity(serviceStatus.status)" /></div>
            <div class="stat-item"><span class="stat-label">Active Since</span><span>{{ serviceStatus.active_since ?? '—' }}</span></div>
            <div class="stat-item"><span class="stat-label">PID</span><span>{{ serviceStatus.pid ?? '—' }}</span></div>
          </div>
        </div>
        <div class="tab-toolbar" style="margin-top: 1rem">
          <Button label="Refresh Status" icon="pi pi-refresh" :loading="statusLoading" @click="loadStatus" />
        </div>
      </TabPanel>
    </TabView>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Textarea from 'primevue/textarea'
import { vpnInstancesApi } from '@/api/vpnInstances'
import type { VpnInstanceRead, VpnInstanceStatus, ServiceAction } from '@/types'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const instanceId = Number(route.params.id)
const instance = ref<VpnInstanceRead | null>(null)
const serviceStatus = ref<VpnInstanceStatus | null>(null)

const logs = ref('')
const logsLoading = ref(false)
const logLines = ref(100)
const logLineOptions = [
  { label: '50 lines', value: 50 },
  { label: '100 lines', value: 100 },
  { label: '200 lines', value: 200 },
  { label: '500 lines', value: 500 },
]

const configDirectives = ref<Record<string, unknown> | null>(null)
const configLoading = ref(false)
const statusLoading = ref(false)
const actionLoading = ref<string | null>(null)
const settingsPamEnabled = ref(false)
const settingsTlsAuthKey = ref('')
const settingsSaving = ref(false)

const serviceActions: { name: ServiceAction; label: string; icon: string; severity: string }[] = [
  { name: 'start', label: 'Start', icon: 'pi pi-play', severity: 'success' },
  { name: 'stop', label: 'Stop', icon: 'pi pi-stop', severity: 'danger' },
  { name: 'restart', label: 'Restart', icon: 'pi pi-refresh', severity: 'warn' },
  { name: 'reload', label: 'Reload', icon: 'pi pi-replay', severity: 'info' },
  { name: 'enable', label: 'Enable', icon: 'pi pi-check-circle', severity: 'success' },
  { name: 'disable', label: 'Disable', icon: 'pi pi-ban', severity: 'secondary' },
]

function statusSeverity(status: string): string {
  if (status === 'active') return 'success'
  if (status === 'inactive') return 'secondary'
  return 'warn'
}

function formatDirectiveValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ')
  if (value === null || value === undefined) return '—'
  return String(value)
}

async function loadInstance() {
  try {
    instance.value = await vpnInstancesApi.get(instanceId)
    settingsPamEnabled.value = instance.value.pam_enabled
    settingsTlsAuthKey.value = instance.value.tls_auth_key ?? ''
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load instance', life: 4000 })
  }
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    instance.value = await vpnInstancesApi.update(instanceId, {
      pam_enabled: settingsPamEnabled.value,
      tls_auth_key: settingsTlsAuthKey.value || null,
    })
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Settings updated.', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to save settings', life: 4000 })
  } finally {
    settingsSaving.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const result = await vpnInstancesApi.getLogs(instanceId, logLines.value)
    logs.value = result.logs
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load logs', life: 4000 })
  } finally {
    logsLoading.value = false
  }
}

async function loadConfig() {
  configLoading.value = true
  try {
    const result = await vpnInstancesApi.getConfig(instanceId)
    configDirectives.value = result.directives
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load config', life: 4000 })
  } finally {
    configLoading.value = false
  }
}

async function loadStatus() {
  statusLoading.value = true
  try {
    serviceStatus.value = await vpnInstancesApi.getStatus(instanceId)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load status', life: 4000 })
  } finally {
    statusLoading.value = false
  }
}

async function runAction(action: ServiceAction) {
  actionLoading.value = action
  try {
    await vpnInstancesApi.serviceAction(instanceId, action)
    toast.add({ severity: 'success', summary: 'Done', detail: `Action "${action}" executed.`, life: 3000 })
    await loadStatus()
    await loadInstance()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? `Failed to ${action}`, life: 4000 })
  } finally {
    actionLoading.value = null
  }
}

onMounted(async () => {
  await loadInstance()
  await Promise.all([loadLogs(), loadConfig(), loadStatus()])
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 1.5rem;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
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
.status-card {
  background: var(--p-surface-100);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.5rem;
}
.stat-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
}
.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.stat-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--p-surface-500);
}
.tab-toolbar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
}
.log-output {
  background: var(--p-surface-900);
  color: var(--p-surface-100);
  padding: 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  line-height: 1.5;
  max-height: 500px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.directive-list {
  border: 1px solid var(--p-surface-200);
  border-radius: 6px;
  overflow: hidden;
}
.directive-row {
  display: flex;
  gap: 1rem;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--p-surface-200);
}
.directive-row:last-child {
  border-bottom: none;
}
.directive-key {
  font-weight: 600;
  min-width: 180px;
  color: var(--p-primary-color);
}
.directive-value {
  word-break: break-all;
}
.service-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.service-status-card {
  background: var(--p-surface-100);
  border-radius: 8px;
  padding: 1rem 1.25rem;
}
.empty-msg {
  padding: 1rem;
  color: var(--p-surface-500);
}
.settings-section {
  max-width: 640px;
  padding: 0.25rem 0;
}
.settings-heading {
  font-size: 1rem;
  font-weight: 700;
  margin: 0 0 1rem;
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
  gap: 0.6rem;
}
.field-inline label {
  margin: 0;
  cursor: pointer;
}
.w-full {
  width: 100%;
}
.text-muted {
  color: var(--p-surface-400);
  font-size: 0.8rem;
}
</style>
