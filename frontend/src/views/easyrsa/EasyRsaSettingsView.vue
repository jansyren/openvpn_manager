<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Easy-RSA Settings</h1>
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
        @change="loadSettings"
      />
    </div>

    <Message v-if="settings?.permission_error" severity="error" :closable="false" style="margin-bottom: 1rem">
      Permission denied reading PKI directory: {{ settings.error_detail }}
      <br />Ensure the SSH user has read access to the PKI directory (e.g. <code>chmod o+x /etc/easy-rsa/pki</code>
      and <code>chmod o+r /etc/easy-rsa/pki/serial /etc/easy-rsa/pki/ca.crt</code>), or add the user to the appropriate group.
    </Message>

    <div v-if="settings" class="settings-card">
      <div class="stat-grid">
        <div class="stat-item">
          <span class="stat-label">EasyRSA Binary</span>
          <span>{{ settings.easyrsa_path ?? '(default)' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">PKI Directory</span>
          <span>{{ settings.pki_dir ?? '(default: /etc/easy-rsa/pki)' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">CA Server</span>
          <span>{{ settings.easyrsa_server_id ? serverName(settings.easyrsa_server_id) : '— same as VPN —' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">PKI Initialized</span>
          <Tag :value="settings.pki_initialized ? 'Yes' : 'No'" :severity="settings.pki_initialized ? 'success' : 'secondary'" />
        </div>
        <div class="stat-item">
          <span class="stat-label">CA Built</span>
          <Tag :value="settings.ca_built ? 'Yes' : 'No'" :severity="settings.ca_built ? 'success' : 'secondary'" />
        </div>
      </div>

      <div class="path-row">
        <InputText v-model="newPath" class="path-input" :placeholder="settings.easyrsa_path ?? '/usr/share/easy-rsa/easyrsa'" />
        <Button label="Update Binary Path" icon="pi pi-save" :loading="updatingPath" @click="updatePath" />
      </div>
      <div class="path-row" style="margin-top: 0.75rem">
        <InputText v-model="newPkiDir" class="path-input" :placeholder="settings.pki_dir ?? '/etc/easy-rsa/pki'" />
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
        <span class="text-muted" style="font-size: 0.8rem">(requires NOPASSWD sudoers entry for the easyrsa binary)</span>
      </div>
    </div>

    <div v-if="selectedInstanceId" class="action-grid">
      <Button label="Init PKI" icon="pi pi-folder-open" severity="info" @click="openInitPkiDialog" />
      <Button label="Build CA" icon="pi pi-shield" severity="success" :disabled="!settings?.pki_initialized" @click="openBuildCaDialog" />
      <Button label="Build Server Cert" icon="pi pi-server" severity="success" :disabled="!settings?.ca_built" @click="openBuildServerDialog" />
      <Button label="Generate DH" icon="pi pi-key" severity="secondary" :disabled="!settings?.pki_initialized" @click="confirmGenDh" />
    </div>

    <!-- CA Management -->
    <div v-if="selectedInstanceId && settings?.ca_built" class="settings-card" style="margin-top: 1rem">
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
      <label>CA Passphrase *</label>
      <InputText v-model="renewCaForm.passphrase" type="password" class="w-full" />
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
      <label>Old CA Passphrase *</label>
      <InputText v-model="crossSignForm.old_ca_passphrase" type="password" class="w-full" />
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
        <label>Passphrase</label>
        <InputText v-model="caForm.passphrase" type="password" class="w-full" placeholder="Leave blank for no passphrase" />
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
        <label>Passphrase</label>
        <InputText v-model="serverForm.passphrase" type="password" class="w-full" placeholder="Leave blank for no passphrase" />
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
import { ref, computed, onMounted } from 'vue'
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
import { useServersStore } from '@/stores/servers'
import { vpnInstancesApi } from '@/api/vpnInstances'
import { easyrsaApi } from '@/api/easyrsa'
import type { EasyRsaSettings, VpnInstanceRead } from '@/types'


const toast = useToast()
const confirm = useConfirm()
const serversStore = useServersStore()

const instances = ref<VpnInstanceRead[]>([])
const settings = ref<EasyRsaSettings | null>(null)
const selectedServerId = ref<number | null>(null)
const selectedInstanceId = ref<number | null>(null)
const newPath = ref('')
const updatingPath = ref(false)
const newPkiDir = ref('')
const updatingPkiDir = ref(false)
const newEasyrsaServerId = ref<number | null>(null)
const updatingServer = ref(false)
const useSudo = ref(false)
const opLoading = ref(false)
const opOutput = ref('')

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

const serverOptions = computed(() =>
  serversStore.servers.map((s) => ({ label: s.name, value: s.id })),
)

function serverName(serverId: number): string {
  return serversStore.servers.find((s) => s.id === serverId)?.name ?? String(serverId)
}

const instanceOptions = computed(() =>
  instances.value.map((i) => ({ label: i.name, value: i.id })),
)

async function onServerChange() {
  selectedInstanceId.value = null
  settings.value = null
  opOutput.value = ''
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

async function loadSettings() {
  if (!selectedInstanceId.value) {
    settings.value = null
    return
  }
  try {
    settings.value = await easyrsaApi.getSettings(selectedInstanceId.value)
    newPath.value = settings.value.easyrsa_path ?? ''
    newPkiDir.value = settings.value.pki_dir ?? ''
    newEasyrsaServerId.value = settings.value.easyrsa_server_id ?? null
    useSudo.value = settings.value.easyrsa_use_sudo ?? false
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load settings', life: 4000 })
  }
}

async function updatePath() {
  if (!selectedInstanceId.value) return
  updatingPath.value = true
  try {
    await easyrsaApi.updatePath(selectedInstanceId.value, newPath.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'EasyRSA path updated.', life: 3000 })
    await loadSettings()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update path', life: 4000 })
  } finally {
    updatingPath.value = false
  }
}

async function updatePkiDir() {
  if (!selectedInstanceId.value) return
  updatingPkiDir.value = true
  try {
    await easyrsaApi.updatePkiDir(selectedInstanceId.value, newPkiDir.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'PKI directory updated.', life: 3000 })
    await loadSettings()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update PKI dir', life: 4000 })
  } finally {
    updatingPkiDir.value = false
  }
}

async function toggleSudo() {
  if (!selectedInstanceId.value) return
  try {
    await easyrsaApi.updateSudo(selectedInstanceId.value, useSudo.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: `sudo ${useSudo.value ? 'enabled' : 'disabled'}.`, life: 3000 })
  } catch (e) {
    useSudo.value = !useSudo.value // revert on failure
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update sudo setting', life: 4000 })
  }
}

async function updateServer() {
  if (!selectedInstanceId.value) return
  updatingServer.value = true
  try {
    await easyrsaApi.updateServer(selectedInstanceId.value, newEasyrsaServerId.value)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'CA server updated.', life: 3000 })
    await loadSettings()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update CA server', life: 4000 })
  } finally {
    updatingServer.value = false
  }
}

function openInitPkiDialog() {
  initPkiForce.value = false
  initPkiVisible.value = true
}

async function doInitPki() {
  opLoading.value = true
  try {
    const result = await easyrsaApi.initPki(selectedInstanceId.value!, initPkiForce.value)
    opOutput.value = (result as { output?: string }).output ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'PKI initialised.', life: 3000 })
    initPkiVisible.value = false
    await loadSettings()
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
  if (!caForm.value.common_name) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Common name is required.', life: 3000 })
    return
  }
  opLoading.value = true
  try {
    const result = await easyrsaApi.buildCa(selectedInstanceId.value!, {
      common_name: caForm.value.common_name,
      passphrase: caForm.value.passphrase || undefined,
      expire_days: caForm.value.expire_days,
    })
    opOutput.value = (result as { output?: string }).output ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'CA built successfully.', life: 3000 })
    buildCaVisible.value = false
    await loadSettings()
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
    const result = await easyrsaApi.buildServer(selectedInstanceId.value!, {
      common_name: serverForm.value.common_name,
      passphrase: serverForm.value.passphrase || undefined,
      expire_days: serverForm.value.expire_days,
    })
    opOutput.value = (result as { output?: string }).output ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'Server certificate built.', life: 3000 })
    buildServerVisible.value = false
    await loadSettings()
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
        const result = await easyrsaApi.genDh(selectedInstanceId.value!)
        opOutput.value = (result as { output?: string }).output ?? JSON.stringify(result, null, 2)
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
  if (!selectedInstanceId.value || !renewCaForm.value.passphrase) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'CA passphrase is required.', life: 3000 })
    return
  }
  opLoading.value = true
  try {
    const result = await easyrsaApi.renewCa(selectedInstanceId.value, {
      ca_passphrase: renewCaForm.value.passphrase,
      expire_days: renewCaForm.value.expire_days,
    })
    opOutput.value = (result as { message?: string }).message ?? JSON.stringify(result, null, 2)
    toast.add({ severity: 'success', summary: 'Done', detail: 'CA certificate renewed.', life: 3000 })
    renewCaVisible.value = false
    await loadSettings()
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
  if (!selectedInstanceId.value || !crossSignForm.value.new_ca_csr_pem || !crossSignForm.value.old_ca_passphrase) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'CSR and passphrase are required.', life: 3000 })
    return
  }
  opLoading.value = true
  try {
    const result = await easyrsaApi.crossSign(selectedInstanceId.value, {
      new_ca_csr_pem: crossSignForm.value.new_ca_csr_pem,
      old_ca_passphrase: crossSignForm.value.old_ca_passphrase,
      expire_days: crossSignForm.value.expire_days,
    })
    opOutput.value = result.cross_cert_pem
    toast.add({ severity: 'success', summary: 'Done', detail: 'Cross-signed certificate generated.', life: 3000 })
    crossSignVisible.value = false
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to cross-sign', life: 4000 })
  } finally {
    opLoading.value = false
  }
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
