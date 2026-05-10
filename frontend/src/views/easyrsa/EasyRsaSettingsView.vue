<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Easy-RSA Settings</h1>
    </div>

    <Message v-if="!ctx.selectedServerId" severity="info" :closable="false" style="margin-bottom:1rem">
      Select a server in the header bar to manage Easy-RSA settings.
    </Message>

    <div v-if="ctx.selectedServerId" class="filter-bar">
      <Select
        v-model="selectedInstanceId"
        :options="[{ label: '— Server-level (no VPN instance) —', value: -1 }, ...instanceOptions]"
        option-label="label"
        option-value="value"
        placeholder="Select mode…"
        class="filter-select"
        @change="onModeChange"
      />
    </div>

    <Message v-if="permissionError" severity="error" :closable="false" style="margin-bottom: 1rem">
      Permission denied reading PKI directory: {{ errorDetail }}
      <br />Ensure the SSH user has read access to the PKI directory, or enable sudo.
    </Message>

    <!-- Settings card: shown when a server is selected and mode is chosen -->
    <div v-if="ctx.selectedServerId && selectedInstanceId !== null" class="settings-card">
      <div class="stat-grid">
        <div class="stat-item">
          <span class="stat-label">EasyRSA Binary</span>
          <span>{{ currentEasyrsaPath || '(default)' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">PKI Directory</span>
          <span>{{ currentPkiDir || '(default: /etc/easy-rsa/pki)' }}</span>
        </div>
        <div v-if="isInstanceMode" class="stat-item">
          <span class="stat-label">CA Server</span>
          <span>{{ settings?.easyrsa_server_id ? serverName(settings.easyrsa_server_id) : '— same as VPN —' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">PKI Initialized</span>
          <Tag :value="pkiInitialized ? 'Yes' : 'No'" :severity="pkiInitialized ? 'success' : 'secondary'" />
        </div>
        <div class="stat-item">
          <span class="stat-label">CA Built</span>
          <Tag :value="caBuilt ? 'Yes' : 'No'" :severity="caBuilt ? 'success' : 'secondary'" />
        </div>
      </div>

      <!-- Server-level: editable path inputs -->
      <div v-if="isServerMode" class="path-row">
        <InputText v-model="serverEasyrsaPath" class="path-input" placeholder="/usr/share/easy-rsa/easyrsa" />
        <span class="path-label">Binary Path <small style="font-weight:400;color:var(--p-surface-400)">(full path to easyrsa executable)</small></span>
      </div>
      <div v-if="isServerMode" class="path-row" style="margin-top: 0.75rem">
        <InputText v-model="serverPkiDir" class="path-input" placeholder="/etc/easy-rsa/pki" />
        <span class="path-label">PKI Directory</span>
      </div>
      <div v-if="isServerMode" class="path-row" style="margin-top: 0.75rem; align-items: center; gap: 0.75rem">
        <Checkbox v-model="serverUseSudo" :binary="true" input-id="server-use-sudo" />
        <label for="server-use-sudo" style="font-weight: 600; cursor: pointer">Run easy-rsa with sudo</label>
        <Button label="Refresh Status" icon="pi pi-refresh" severity="secondary" size="small" :loading="statusLoading" @click="loadServerStatus" style="margin-left: auto" />
      </div>

      <!-- Instance-level: path update controls -->
      <template v-if="isInstanceMode">
        <div class="path-row">
          <InputText v-model="newPath" class="path-input" :placeholder="settings?.easyrsa_path ?? '/usr/share/easy-rsa/easyrsa'" />
          <Button label="Update Binary Path" icon="pi pi-save" :loading="updatingPath" @click="updatePath" />
        </div>
        <div class="path-row" style="margin-top: 0.75rem">
          <InputText v-model="newPkiDir" class="path-input" :placeholder="settings?.pki_dir ?? '/etc/easy-rsa/pki'" />
          <Button label="Update PKI Dir" icon="pi pi-save" :loading="updatingPkiDir" @click="updatePkiDir" />
        </div>
        <div class="path-row" style="margin-top: 0.75rem">
          <Select
            v-model="newEasyrsaServerId"
            :options="[{ label: '— Same as VPN server —', value: null }, ...serverOptions]"
            option-label="label"
            option-value="value"
            class="path-input"
            placeholder="CA Server"
          />
          <Button label="Update CA Server" icon="pi pi-save" :loading="updatingServer" @click="updateServer" />
        </div>
        <div class="path-row" style="margin-top: 0.75rem; align-items: center; gap: 0.75rem">
          <Checkbox v-model="useSudo" :binary="true" input-id="use-sudo" @change="toggleSudo" />
          <label for="use-sudo" style="font-weight: 600; cursor: pointer">Run easy-rsa with sudo</label>
          <span class="text-muted" style="font-size: 0.8rem">(requires NOPASSWD sudoers entry or a configured sudo password)</span>
        </div>

        <!-- CA Passphrase Storage -->
        <div class="ca-passphrase-row" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--p-surface-200)">
          <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.75rem">
            <span style="font-weight:600; font-size:0.9rem">Stored CA Passphrase</span>
            <Tag
              v-if="selectedInstanceHasCaPassphrase"
              value="Stored"
              severity="success"
              icon="pi pi-lock"
            />
            <Tag v-else value="Not stored" severity="secondary" icon="pi pi-lock-open" />
            <span class="text-muted" style="font-size:0.8rem; margin-left:auto">
              Operators can generate/revoke certs without knowing the passphrase
            </span>
          </div>
          <div class="path-row">
            <InputText
              v-model="caPassphraseInput"
              type="password"
              class="path-input"
              placeholder="Enter CA passphrase to store…"
              autocomplete="new-password"
            />
            <Button label="Store" icon="pi pi-save" :loading="savingCaPassphrase" @click="saveCaPassphrase" />
            <Button
              v-if="selectedInstanceHasCaPassphrase"
              label="Clear"
              icon="pi pi-times"
              severity="secondary"
              :loading="savingCaPassphrase"
              @click="clearCaPassphrase"
            />
          </div>
        </div>
      </template>
    </div>

    <div v-if="ctx.selectedServerId && selectedInstanceId !== null" class="action-grid">
      <Button label="Init PKI" icon="pi pi-folder-open" severity="info" @click="openInitPkiDialog" />
      <Button label="Build CA" icon="pi pi-shield" severity="success" :disabled="!pkiInitialized" @click="openBuildCaDialog" />
      <Button label="Build Server Cert" icon="pi pi-server" severity="success" :disabled="!caBuilt" @click="openBuildServerDialog" />
      <Button label="Generate DH" icon="pi pi-key" severity="secondary" :disabled="!pkiInitialized" @click="confirmGenDh" />
    </div>

    <!-- CA Management -->
    <div v-if="ctx.selectedServerId && selectedInstanceId !== null && caBuilt" class="settings-card" style="margin-top: 1rem">
      <h3 style="margin:0 0 1rem;font-size:1rem;font-weight:700;">CA Management</h3>
      <div class="action-grid">
        <Button label="Renew CA" icon="pi pi-refresh" severity="warn" @click="openRenewCaDialog" />
        <Button label="Generate Cross-Signed Cert" icon="pi pi-share-alt" severity="secondary" @click="openCrossSignDialog" />
      </div>
    </div>

    <div v-if="opOutput" class="op-output-wrap">
      <h3 class="op-output-title">Operation Output</h3>
      <pre class="op-output">{{ opOutput }}</pre>
    </div>

    <!-- Init PKI Dialog -->
    <Dialog v-model:visible="initPkiVisible" header="Init PKI" modal style="width: 400px">
      <p>This will initialise a new PKI directory.</p>
      <div class="field field-inline">
        <Checkbox v-model="initPkiForce" :binary="true" input-id="force-init" />
        <label for="force-init">Force (overwrite existing)</label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="initPkiVisible = false" />
        <Button label="Init PKI" :loading="opLoading" @click="doInitPki" />
      </template>
    </Dialog>

    <!-- Renew CA Dialog -->
    <Dialog v-model:visible="renewCaVisible" header="Renew CA Certificate" modal style="width: 440px">
      <p>Re-sign the CA with the same key to extend its validity. Existing issued certificates remain valid.</p>
      <div class="field">
        <label>CA Passphrase <span v-if="!selectedInstanceHasCaPassphrase">*</span></label>
        <InputText v-model="renewCaForm.passphrase" type="password" class="w-full" :placeholder="selectedInstanceHasCaPassphrase ? 'Using stored passphrase' : ''" />
        <small v-if="selectedInstanceHasCaPassphrase" class="text-muted">Leave blank to use the stored passphrase.</small>
      </div>
      <div class="field">
        <label>Expire Days</label>
        <InputNumber v-model="renewCaForm.expire_days" class="w-full" :min="1" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="renewCaVisible = false" />
        <Button label="Renew CA" severity="warn" :loading="opLoading" @click="doRenewCa" />
      </template>
    </Dialog>

    <!-- Cross-Sign Dialog -->
    <Dialog v-model:visible="crossSignVisible" header="Generate Cross-Signed Certificate" modal style="width: 500px">
      <p>Sign a new CA's CSR with this CA's key to create a cross-certificate for seamless CA migration.</p>
      <div class="field">
        <label>New CA CSR (PEM) *</label>
        <Textarea v-model="crossSignForm.new_ca_csr_pem" class="w-full" rows="6" placeholder="-----BEGIN CERTIFICATE REQUEST-----..." />
      </div>
      <div class="field">
        <label>Old CA Passphrase <span v-if="!selectedInstanceHasCaPassphrase">*</span></label>
        <InputText v-model="crossSignForm.old_ca_passphrase" type="password" class="w-full" :placeholder="selectedInstanceHasCaPassphrase ? 'Using stored passphrase' : ''" />
        <small v-if="selectedInstanceHasCaPassphrase" class="text-muted">Leave blank to use the stored passphrase.</small>
      </div>
      <div class="field">
        <label>Expire Days</label>
        <InputNumber v-model="crossSignForm.expire_days" class="w-full" :min="1" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="crossSignVisible = false" />
        <Button label="Cross-Sign" severity="info" :loading="opLoading" @click="doCrossSign" />
      </template>
    </Dialog>

    <!-- Build CA Dialog -->
    <Dialog v-model:visible="buildCaVisible" header="Build CA" modal style="width: 440px">
      <div class="field">
        <label>Common Name *</label>
        <InputText v-model="caForm.common_name" class="w-full" placeholder="Easy-RSA CA" />
      </div>
      <div class="field">
        <label>Passphrase *</label>
        <InputText v-model="caForm.passphrase" type="password" class="w-full" />
      </div>
      <div class="field">
        <label>Expire Days</label>
        <InputNumber v-model="caForm.expire_days" class="w-full" :min="1" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="buildCaVisible = false" />
        <Button label="Build CA" severity="success" :loading="opLoading" @click="doBuildCa" />
      </template>
    </Dialog>

    <!-- Build Server Cert Dialog -->
    <Dialog v-model:visible="buildServerVisible" header="Build Server Certificate" modal style="width: 440px">
      <div class="field">
        <label>Common Name *</label>
        <InputText v-model="serverForm.common_name" class="w-full" placeholder="server" />
      </div>
      <div class="field">
        <label>CA Passphrase</label>
        <InputText v-model="serverForm.passphrase" type="password" class="w-full" />
      </div>
      <div class="field">
        <label>Expire Days</label>
        <InputNumber v-model="serverForm.expire_days" class="w-full" :min="1" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="buildServerVisible = false" />
        <Button label="Build Cert" severity="success" :loading="opLoading" @click="doBuildServer" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import Textarea from 'primevue/textarea'
import { useContextStore } from '@/stores/context'
import { vpnInstancesApi } from '@/api/vpnInstances'
import { easyrsaApi } from '@/api/easyrsa'
import type { EasyRsaSettings } from '@/types'

const toast = useToast()
const confirm = useConfirm()
const ctx = useContextStore()

const settings = ref<EasyRsaSettings | null>(null)
// -1 = server-level mode, >0 = VPN instance mode, null = nothing selected
const selectedInstanceId = ref<number | null>(ctx.selectedInstanceId ?? -1)

// Server-level settings (editable)
const serverEasyrsaPath = ref('/usr/share/easy-rsa/easyrsa')
const serverPkiDir = ref('/etc/easy-rsa/pki')
const serverUseSudo = ref(false)
const statusLoading = ref(false)

// Server-level PKI status
const serverPkiInitialized = ref(false)
const serverCaBuilt = ref(false)

// Instance-level settings
const newPath = ref('')
const updatingPath = ref(false)
const newPkiDir = ref('')
const updatingPkiDir = ref(false)
const newEasyrsaServerId = ref<number | null>(null)
const updatingServer = ref(false)
const useSudo = ref(false)

// Operation state
const opLoading = ref(false)
const opOutput = ref('')

// Permission error state
const permissionError = ref(false)
const errorDetail = ref<string | null>(null)

// Dialog state
const initPkiVisible = ref(false)
const initPkiForce = ref(false)

const renewCaVisible = ref(false)
const renewCaForm = ref({ passphrase: '', expire_days: 3650 })

const crossSignVisible = ref(false)
const crossSignForm = ref({ new_ca_csr_pem: '', old_ca_passphrase: '', expire_days: 365 })

const buildCaVisible = ref(false)
const caForm = ref({ common_name: 'Easy-RSA CA', passphrase: '', expire_days: 3650 })

const buildServerVisible = ref(false)
const serverForm = ref({ common_name: 'server', passphrase: '', expire_days: 825 })

// CA passphrase storage
const caPassphraseInput = ref('')
const savingCaPassphrase = ref(false)

// Computed
const isServerMode = computed(() => selectedInstanceId.value === -1)
const isInstanceMode = computed(() => selectedInstanceId.value !== null && selectedInstanceId.value > 0)

const pkiInitialized = computed(() => isServerMode.value ? serverPkiInitialized.value : (settings.value?.pki_initialized ?? false))
const caBuilt = computed(() => isServerMode.value ? serverCaBuilt.value : (settings.value?.ca_built ?? false))

const currentEasyrsaPath = computed(() => isServerMode.value ? serverEasyrsaPath.value : (settings.value?.easyrsa_path ?? ''))
const currentPkiDir = computed(() => isServerMode.value ? serverPkiDir.value : (settings.value?.pki_dir ?? ''))

const serverLevelParams = computed(() => ({
  easyrsa_path: serverEasyrsaPath.value,
  pki_dir: serverPkiDir.value,
  use_sudo: serverUseSudo.value,
}))

const serverOptions = computed(() =>
  ctx.servers.map((s) => ({ label: s.name, value: s.id })),
)

function serverName(serverId: number): string {
  return ctx.servers.find((s) => s.id === serverId)?.name ?? String(serverId)
}

const instanceOptions = computed(() =>
  ctx.instances.map((i) => ({ label: i.name, value: i.id })),
)

const selectedInstance = computed(() =>
  ctx.instances.find((i) => i.id === selectedInstanceId.value) ?? null,
)

const selectedInstanceHasCaPassphrase = computed(() =>
  isInstanceMode.value && (selectedInstance.value?.has_ca_passphrase ?? false),
)

watch(
  () => ctx.selectedServerId,
  () => {
    selectedInstanceId.value = null
    settings.value = null
    opOutput.value = ''
    permissionError.value = false
    errorDetail.value = null
    serverPkiInitialized.value = false
    serverCaBuilt.value = false
  },
)

async function onModeChange() {
  opOutput.value = ''
  permissionError.value = false
  errorDetail.value = null
  if (selectedInstanceId.value === -1) {
    // Server-level mode
    settings.value = null
    await loadServerStatus()
  } else if (selectedInstanceId.value && selectedInstanceId.value > 0) {
    await loadInstanceSettings()
  } else {
    settings.value = null
  }
}

async function loadServerStatus() {
  if (!ctx.selectedServerId) return
  statusLoading.value = true
  try {
    const result = await easyrsaApi.serverPkiStatus(ctx.selectedServerId, serverLevelParams.value)
    serverPkiInitialized.value = result.pki_initialized
    serverCaBuilt.value = result.ca_built
    permissionError.value = result.permission_error
    errorDetail.value = result.error_detail ?? null
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load PKI status', life: 4000 })
  } finally {
    statusLoading.value = false
  }
}

async function loadInstanceSettings() {
  if (!selectedInstanceId.value || selectedInstanceId.value <= 0) {
    settings.value = null
    return
  }
  try {
    settings.value = await easyrsaApi.getSettings(selectedInstanceId.value)
    newPath.value = settings.value.easyrsa_path ?? ''
    newPkiDir.value = settings.value.pki_dir ?? ''
    newEasyrsaServerId.value = settings.value.easyrsa_server_id ?? null
    useSudo.value = settings.value.easyrsa_use_sudo ?? false
    permissionError.value = settings.value.permission_error
    errorDetail.value = settings.value.error_detail ?? null
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load settings', life: 4000 })
  }
}

async function saveCaPassphrase() {
  if (!selectedInstanceId.value || selectedInstanceId.value <= 0) return
  if (!caPassphraseInput.value) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Enter a passphrase to store.', life: 3000 })
    return
  }
  savingCaPassphrase.value = true
  try {
    const updated = await vpnInstancesApi.setCaPassphrase(selectedInstanceId.value, caPassphraseInput.value)
    // Update local instance list to reflect new has_ca_passphrase state
    const idx = ctx.instances.findIndex((i) => i.id === selectedInstanceId.value)
    if (idx !== -1) ctx.instances[idx] = updated
    caPassphraseInput.value = ''
    toast.add({ severity: 'success', summary: 'Stored', detail: 'CA passphrase stored securely.', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to store passphrase', life: 4000 })
  } finally {
    savingCaPassphrase.value = false
  }
}

async function clearCaPassphrase() {
  if (!selectedInstanceId.value || selectedInstanceId.value <= 0) return
  savingCaPassphrase.value = true
  try {
    const updated = await vpnInstancesApi.setCaPassphrase(selectedInstanceId.value, null)
    const idx = ctx.instances.findIndex((i) => i.id === selectedInstanceId.value)
    if (idx !== -1) ctx.instances[idx] = updated
    toast.add({ severity: 'success', summary: 'Cleared', detail: 'Stored CA passphrase removed.', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to clear passphrase', life: 4000 })
  } finally {
    savingCaPassphrase.value = false
  }
}

// Instance-level update operations
async function updatePath() {
  if (!selectedInstanceId.value || selectedInstanceId.value <= 0) return
  updatingPath.value = true
  try {
    await easyrsaApi.updatePath(selectedInstanceId.value, newPath.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'EasyRSA path updated.', life: 3000 })
    await loadInstanceSettings()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update path', life: 4000 })
  } finally {
    updatingPath.value = false
  }
}

async function updatePkiDir() {
  if (!selectedInstanceId.value || selectedInstanceId.value <= 0) return
  updatingPkiDir.value = true
  try {
    await easyrsaApi.updatePkiDir(selectedInstanceId.value, newPkiDir.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'PKI directory updated.', life: 3000 })
    await loadInstanceSettings()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update PKI dir', life: 4000 })
  } finally {
    updatingPkiDir.value = false
  }
}

async function toggleSudo() {
  if (!selectedInstanceId.value || selectedInstanceId.value <= 0) return
  try {
    await easyrsaApi.updateSudo(selectedInstanceId.value, useSudo.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: `sudo ${useSudo.value ? 'enabled' : 'disabled'}.`, life: 3000 })
  } catch (e) {
    useSudo.value = !useSudo.value
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update sudo setting', life: 4000 })
  }
}

async function updateServer() {
  if (!selectedInstanceId.value || selectedInstanceId.value <= 0) return
  updatingServer.value = true
  try {
    await easyrsaApi.updateServer(selectedInstanceId.value, newEasyrsaServerId.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'CA server updated.', life: 3000 })
    await loadInstanceSettings()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update CA server', life: 4000 })
  } finally {
    updatingServer.value = false
  }
}

// ── Operations (work in both modes) ────────────────────────────────────

function openInitPkiDialog() {
  initPkiForce.value = false
  initPkiVisible.value = true
}

async function doInitPki() {
  opLoading.value = true
  try {
    let result: { output?: string }
    if (isServerMode.value) {
      result = await easyrsaApi.serverInitPki(ctx.selectedServerId!, { ...serverLevelParams.value, force: initPkiForce.value })
    } else {
      result = await easyrsaApi.initPki(selectedInstanceId.value!, initPkiForce.value)
    }
    opOutput.value = result.output ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'PKI initialised.', life: 3000 })
    initPkiVisible.value = false
    await refreshStatus()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to init PKI', life: 4000 })
  } finally {
    opLoading.value = false
  }
}

function openBuildCaDialog() {
  caForm.value = { common_name: 'Easy-RSA CA', passphrase: '', expire_days: 3650 }
  buildCaVisible.value = true
}

async function doBuildCa() {
  if (!caForm.value.common_name || !caForm.value.passphrase) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Common name and passphrase are required.', life: 3000 })
    return
  }
  opLoading.value = true
  try {
    let result: { output?: string }
    if (isServerMode.value) {
      result = await easyrsaApi.serverBuildCa(ctx.selectedServerId!, {
        ...serverLevelParams.value,
        common_name: caForm.value.common_name,
        passphrase: caForm.value.passphrase,
        expire_days: caForm.value.expire_days,
      })
    } else {
      result = await easyrsaApi.buildCa(selectedInstanceId.value!, {
        common_name: caForm.value.common_name,
        passphrase: caForm.value.passphrase,
        expire_days: caForm.value.expire_days,
      })
    }
    opOutput.value = result.output ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'CA built successfully.', life: 3000 })
    buildCaVisible.value = false
    await refreshStatus()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to build CA', life: 4000 })
  } finally {
    opLoading.value = false
  }
}

function openBuildServerDialog() {
  serverForm.value = { common_name: 'server', passphrase: '', expire_days: 825 }
  buildServerVisible.value = true
}

async function doBuildServer() {
  if (!serverForm.value.common_name) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Common name is required.', life: 3000 })
    return
  }
  opLoading.value = true
  try {
    let result: { output?: string }
    if (isServerMode.value) {
      result = await easyrsaApi.serverBuildServer(ctx.selectedServerId!, {
        ...serverLevelParams.value,
        common_name: serverForm.value.common_name,
        passphrase: serverForm.value.passphrase || undefined,
        expire_days: serverForm.value.expire_days,
      })
    } else {
      result = await easyrsaApi.buildServer(selectedInstanceId.value!, {
        common_name: serverForm.value.common_name,
        passphrase: serverForm.value.passphrase || undefined,
        expire_days: serverForm.value.expire_days,
      })
    }
    opOutput.value = result.output ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'Server certificate built.', life: 3000 })
    buildServerVisible.value = false
    await refreshStatus()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to build server cert', life: 4000 })
  } finally {
    opLoading.value = false
  }
}

function confirmGenDh() {
  confirm.require({
    message: 'Generate Diffie-Hellman parameters? This may take a while.',
    header: 'Generate DH',
    icon: 'pi pi-key',
    severity: 'warn',
    accept: async () => {
      opLoading.value = true
      try {
        let result: { output?: string }
        if (isServerMode.value) {
          result = await easyrsaApi.serverGenDh(ctx.selectedServerId!, serverLevelParams.value)
        } else {
          result = await easyrsaApi.genDh(selectedInstanceId.value!)
        }
        opOutput.value = result.output ?? JSON.stringify(result, null, 2)
        toast.add({ severity: 'success', summary: 'Done', detail: 'DH parameters generated.', life: 3000 })
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to generate DH', life: 4000 })
      } finally {
        opLoading.value = false
      }
    },
  })
}

function openRenewCaDialog() {
  renewCaForm.value = { passphrase: '', expire_days: 3650 }
  renewCaVisible.value = true
}

async function doRenewCa() {
  if (!renewCaForm.value.passphrase && !selectedInstanceHasCaPassphrase.value) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'CA passphrase is required.', life: 3000 })
    return
  }
  opLoading.value = true
  try {
    let result: { message?: string }
    if (isServerMode.value) {
      result = await easyrsaApi.serverRenewCa(ctx.selectedServerId!, {
        ...serverLevelParams.value,
        ca_passphrase: renewCaForm.value.passphrase,
        expire_days: renewCaForm.value.expire_days,
      })
    } else {
      result = await easyrsaApi.renewCa(selectedInstanceId.value!, {
        ca_passphrase: renewCaForm.value.passphrase,
        expire_days: renewCaForm.value.expire_days,
      })
    }
    opOutput.value = result.message ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'CA certificate renewed.', life: 3000 })
    renewCaVisible.value = false
    await refreshStatus()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to renew CA', life: 4000 })
  } finally {
    opLoading.value = false
  }
}

function openCrossSignDialog() {
  crossSignForm.value = { new_ca_csr_pem: '', old_ca_passphrase: '', expire_days: 365 }
  crossSignVisible.value = true
}

async function doCrossSign() {
  if (!crossSignForm.value.new_ca_csr_pem || (!crossSignForm.value.old_ca_passphrase && !selectedInstanceHasCaPassphrase.value)) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'CSR and passphrase are required.', life: 3000 })
    return
  }
  opLoading.value = true
  try {
    let result: { cross_cert_pem?: string; message?: string }
    if (isServerMode.value) {
      result = await easyrsaApi.serverCrossSign(ctx.selectedServerId!, {
        ...serverLevelParams.value,
        new_ca_csr_pem: crossSignForm.value.new_ca_csr_pem,
        old_ca_passphrase: crossSignForm.value.old_ca_passphrase,
        expire_days: crossSignForm.value.expire_days,
      })
    } else {
      result = await easyrsaApi.crossSign(selectedInstanceId.value!, {
        new_ca_csr_pem: crossSignForm.value.new_ca_csr_pem,
        old_ca_passphrase: crossSignForm.value.old_ca_passphrase,
        expire_days: crossSignForm.value.expire_days,
      })
    }
    opOutput.value = result.cross_cert_pem ?? result.message ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'Cross-signed certificate generated.', life: 3000 })
    crossSignVisible.value = false
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to cross-sign', life: 4000 })
  } finally {
    opLoading.value = false
  }
}

async function refreshStatus() {
  if (isServerMode.value) {
    await loadServerStatus()
  } else {
    await loadInstanceSettings()
  }
}

onMounted(async () => {
  if (ctx.selectedServerId && selectedInstanceId.value !== null) {
    await onModeChange()
  }
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
.settings-card {
  background: var(--p-surface-100);
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.5rem;
}
.stat-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  margin-bottom: 1.25rem;
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
.path-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.path-input {
  flex: 1;
}
.path-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-surface-500);
  min-width: 100px;
}
.action-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.op-output-wrap {
  margin-top: 1rem;
}
.op-output-title {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  font-weight: 600;
}
.op-output {
  background: var(--p-surface-900);
  color: var(--p-surface-100);
  padding: 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  line-height: 1.5;
  max-height: 400px;
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
