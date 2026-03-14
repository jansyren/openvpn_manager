<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Deployment</h1>
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
      <Button
        label="Check Prerequisites"
        icon="pi pi-search"
        :loading="checkingPrereqs"
        :disabled="!selectedServerId"
        @click="checkPrerequisites"
      />
    </div>

    <!-- Prerequisites Card -->
    <div v-if="prerequisites" class="prereq-card">
      <h3 class="section-title">Prerequisites</h3>
      <div class="stat-grid">
        <div class="stat-item">
          <span class="stat-label">OS Version</span>
          <span>{{ prerequisites.os_version ?? '—' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">OS Compatible</span>
          <Tag :value="prerequisites.os_compatible ? 'Yes' : 'No'" :severity="prerequisites.os_compatible ? 'success' : 'danger'" />
        </div>
        <div class="stat-item">
          <span class="stat-label">OpenVPN</span>
          <Tag :value="prerequisites.openvpn_installed ? 'Installed' : 'Missing'" :severity="prerequisites.openvpn_installed ? 'success' : 'warn'" />
        </div>
        <div class="stat-item">
          <span class="stat-label">EasyRSA</span>
          <Tag :value="prerequisites.easyrsa_installed ? 'Installed' : 'Missing'" :severity="prerequisites.easyrsa_installed ? 'success' : 'warn'" />
        </div>
        <div class="stat-item">
          <span class="stat-label">Disk Space</span>
          <span>{{ prerequisites.disk_space_gb != null ? `${prerequisites.disk_space_gb} GB` : '—' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Ready</span>
          <Tag :value="prerequisites.ready_to_deploy ? 'Ready' : 'Not Ready'" :severity="prerequisites.ready_to_deploy ? 'success' : 'danger'" />
        </div>
      </div>
      <ul v-if="prerequisites.notes.length" class="notes-list">
        <li v-for="(note, i) in prerequisites.notes" :key="i">{{ note }}</li>
      </ul>
    </div>

    <!-- Deploy Options -->
    <div v-if="prerequisites" class="deploy-options">
      <h3 class="section-title">Deployment Options</h3>
      <div class="field field-inline">
        <Checkbox v-model="deployOptions.install_openvpn" :binary="true" input-id="inst-openvpn" />
        <label for="inst-openvpn">Install OpenVPN</label>
      </div>
      <div class="field field-inline">
        <Checkbox v-model="deployOptions.install_easyrsa" :binary="true" input-id="inst-easyrsa" />
        <label for="inst-easyrsa">Install EasyRSA</label>
      </div>
      <div class="field">
        <label>OpenVPN Config Dir</label>
        <InputText v-model="deployOptions.openvpn_config_dir" class="w-full" placeholder="/etc/openvpn" />
      </div>
      <div class="field">
        <label>EasyRSA Install Dir</label>
        <InputText v-model="deployOptions.easyrsa_install_dir" class="w-full" placeholder="/usr/share/easy-rsa" />
      </div>
      <Button
        label="Deploy"
        icon="pi pi-cloud-upload"
        severity="success"
        :disabled="!prerequisites.ready_to_deploy"
        :loading="deploying"
        @click="startDeploy"
      />
    </div>

    <!-- Deploy Log -->
    <div v-if="taskStatus" class="deploy-log-wrap">
      <h3 class="section-title">
        Deployment Log
        <Tag :value="taskStatus.status" :severity="taskStatusSeverity(taskStatus.status)" class="status-tag" />
      </h3>
      <pre ref="logRef" class="deploy-log">{{ taskStatus.log_lines.join('\n') || '…' }}</pre>
      <Message v-if="taskStatus.status === 'completed'" severity="success" :closable="false">Deployment completed successfully.</Message>
      <Message v-if="taskStatus.status === 'failed'" severity="error" :closable="false">
        Deployment failed: {{ taskStatus.error ?? 'Unknown error' }}
      </Message>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, nextTick } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import { useServersStore } from '@/stores/servers'
import { deployApi } from '@/api/deploy'
import type { DeployPrerequisites, DeployTaskStatus } from '@/types'

const toast = useToast()
const serversStore = useServersStore()

const selectedServerId = ref<number | null>(null)
const checkingPrereqs = ref(false)
const prerequisites = ref<DeployPrerequisites | null>(null)
const deploying = ref(false)
const taskStatus = ref<DeployTaskStatus | null>(null)
const pollInterval = ref<ReturnType<typeof setInterval> | null>(null)
const logRef = ref<HTMLPreElement | null>(null)

const deployOptions = ref({
  install_openvpn: false,
  install_easyrsa: false,
  openvpn_config_dir: '/etc/openvpn',
  easyrsa_install_dir: '/usr/share/easy-rsa',
})

const serverOptions = computed(() =>
  serversStore.servers.map((s) => ({ label: s.name, value: s.id })),
)

function taskStatusSeverity(status: string): string {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'info'
  return 'secondary'
}

function onServerChange() {
  prerequisites.value = null
  taskStatus.value = null
  stopPolling()
}

async function checkPrerequisites() {
  if (!selectedServerId.value) return
  checkingPrereqs.value = true
  try {
    prerequisites.value = await deployApi.checkPrerequisites(selectedServerId.value)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to check prerequisites', life: 4000 })
  } finally {
    checkingPrereqs.value = false
  }
}

async function startDeploy() {
  if (!selectedServerId.value) return
  deploying.value = true
  taskStatus.value = null
  stopPolling()
  try {
    const result = await deployApi.startDeployment(selectedServerId.value, {
      install_openvpn: deployOptions.value.install_openvpn,
      install_easyrsa: deployOptions.value.install_easyrsa,
      openvpn_config_dir: deployOptions.value.openvpn_config_dir,
      easyrsa_install_dir: deployOptions.value.easyrsa_install_dir,
    })
    const taskId = (result as { task_id: string }).task_id
    taskStatus.value = { task_id: taskId, status: 'pending', log_lines: [], error: null }
    startPolling(taskId)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to start deployment', life: 4000 })
    deploying.value = false
  }
}

function startPolling(taskId: string) {
  pollInterval.value = setInterval(async () => {
    try {
      const status = await deployApi.getStatus(taskId)
      taskStatus.value = status
      await nextTick()
      if (logRef.value) {
        logRef.value.scrollTop = logRef.value.scrollHeight
      }
      if (status.status === 'completed' || status.status === 'failed') {
        stopPolling()
        deploying.value = false
      }
    } catch {
      // silently ignore poll errors
    }
  }, 2000)
}

function stopPolling() {
  if (pollInterval.value !== null) {
    clearInterval(pollInterval.value)
    pollInterval.value = null
  }
}

onBeforeUnmount(() => {
  stopPolling()
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
.filter-bar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}
.filter-select {
  min-width: 220px;
}
.prereq-card,
.deploy-options {
  background: var(--p-surface-100);
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}
.section-title {
  margin: 0 0 1rem;
  font-size: 1rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.status-tag {
  font-size: 0.75rem;
}
.stat-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  margin-bottom: 0.75rem;
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
.notes-list {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
  font-size: 0.875rem;
  color: var(--p-surface-600);
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
.deploy-log-wrap {
  margin-top: 1rem;
}
.deploy-log {
  background: var(--p-surface-900);
  color: var(--p-surface-100);
  padding: 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  line-height: 1.5;
  height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin-bottom: 1rem;
}
</style>
