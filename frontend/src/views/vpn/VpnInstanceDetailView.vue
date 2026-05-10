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
      <!-- Config Editor Tab -->
      <TabPanel header="Config Editor">
        <div class="tab-toolbar">
          <Button label="Load from Server" icon="pi pi-refresh" severity="secondary" :loading="configLoading" @click="loadConfig" />
          <Button label="Save Config" icon="pi pi-save" severity="success" :loading="configSaving" @click="saveConfig" />
        </div>

        <div v-if="directives.length > 0" class="config-editor">
          <div v-for="cat in categories" :key="cat" class="category-section">
            <h3 class="category-title">{{ categoryLabels[cat] || cat }}</h3>
            <div class="directive-grid">
              <template v-for="d in directivesByCategory(cat)" :key="d.name">
                <!-- Flag directive: checkbox -->
                <div v-if="d.directive_type === 'flag'" class="directive-field directive-flag" :class="{ 'directive-blocked': conflictingDirective(d) }">
                  <Checkbox
                    v-model="configForm[d.name]"
                    :binary="true"
                    :input-id="'d-' + d.name"
                    :disabled="!!conflictingDirective(d)"
                  />
                  <label :for="'d-' + d.name" class="directive-name clickable">{{ d.name }}</label>
                  <span v-if="conflictingDirective(d)" class="conflict-badge" :title="`Cannot be used together with '${conflictingDirective(d)}'`">
                    <i class="pi pi-ban" /> conflicts with <strong>{{ conflictingDirective(d) }}</strong>
                  </span>
                  <span v-else class="directive-desc">{{ d.description }}</span>
                </div>

                <!-- Single directive with allowed_values: dropdown -->
                <div v-else-if="d.directive_type === 'single' && d.allowed_values" class="directive-field" :class="{ 'directive-blocked': conflictingDirective(d) }">
                  <label :for="'d-' + d.name" class="directive-name">{{ d.name }}</label>
                  <div class="input-with-conflict">
                    <Select
                      v-model="configForm[d.name]"
                      :options="directiveOptions(d)"
                      option-label="label"
                      option-value="value"
                      :input-id="'d-' + d.name"
                      show-clear
                      placeholder="(not set)"
                      class="directive-input"
                      :disabled="!!conflictingDirective(d)"
                    />
                    <span v-if="conflictingDirective(d)" class="conflict-badge" :title="`Cannot be used together with '${conflictingDirective(d)}'`">
                      <i class="pi pi-ban" /> conflicts with <strong>{{ conflictingDirective(d) }}</strong>
                    </span>
                  </div>
                  <span class="directive-desc">{{ d.description }}</span>
                </div>

                <!-- Single directive: text input -->
                <div v-else-if="d.directive_type === 'single'" class="directive-field" :class="{ 'directive-blocked': conflictingDirective(d) }">
                  <label :for="'d-' + d.name" class="directive-name">{{ d.name }}</label>
                  <div class="input-with-conflict">
                    <InputText
                      v-model="configForm[d.name]"
                      :input-id="'d-' + d.name"
                      :placeholder="d.example || d.default || ''"
                      class="directive-input"
                      :disabled="!!conflictingDirective(d)"
                    />
                    <span v-if="conflictingDirective(d)" class="conflict-badge" :title="`Cannot be used together with '${conflictingDirective(d)}'`">
                      <i class="pi pi-ban" /> conflicts with <strong>{{ conflictingDirective(d) }}</strong>
                    </span>
                  </div>
                  <span class="directive-desc">{{ d.description }}</span>
                </div>

                <!-- Multi directive: add/remove list -->
                <div v-else-if="d.directive_type === 'multi'" class="directive-field directive-multi" :class="{ 'directive-blocked': conflictingDirective(d) }">
                  <label class="directive-name">{{ d.name }}</label>
                  <div class="multi-entries">
                    <span v-if="conflictingDirective(d)" class="conflict-badge" :title="`Cannot be used together with '${conflictingDirective(d)}'`">
                      <i class="pi pi-ban" /> conflicts with <strong>{{ conflictingDirective(d) }}</strong>
                    </span>
                    <template v-else>
                      <div v-for="(entry, idx) in getMultiValues(d.name)" :key="idx" class="multi-entry">
                        <InputText
                          :model-value="entry"
                          @update:model-value="updateMultiValue(d.name, idx, $event as string)"
                          :placeholder="d.example || ''"
                          class="multi-input"
                        />
                        <Button icon="pi pi-times" severity="danger" text rounded size="small" @click="removeMultiValue(d.name, idx)" />
                      </div>
                      <Button :label="'Add ' + d.name" icon="pi pi-plus" size="small" severity="secondary" @click="addMultiValue(d.name)" />
                    </template>
                  </div>
                  <span class="directive-desc">{{ d.description }}</span>
                </div>
              </template>
            </div>
          </div>

          <!-- PKI Integration section -->
          <div class="category-section">
            <h3 class="category-title">PKI Integration</h3>
            <div class="directive-grid">
              <div class="directive-field">
                <label class="directive-name">Server Certificate</label>
                <div style="display: flex; gap: 0.5rem; align-items: center; width: 100%">
                  <Select
                    v-model="selectedCertCn"
                    :options="pkiCertOptions"
                    option-label="label"
                    option-value="value"
                    placeholder="Select issued certificate"
                    show-clear
                    class="directive-input"
                    :disabled="pkiCerts.length === 0"
                  />
                  <Button
                    label="Install"
                    icon="pi pi-download"
                    severity="info"
                    size="small"
                    :disabled="!selectedCertCn"
                    :loading="installCertLoading"
                    @click="installCert"
                    style="white-space: nowrap"
                  />
                  <Button
                    icon="pi pi-refresh"
                    severity="secondary"
                    size="small"
                    :loading="pkiCertsLoading"
                    @click="loadPkiCerts"
                    v-tooltip="'Refresh cert list from PKI'"
                  />
                </div>
                <span class="directive-desc">
                  Copies cert, key, and CA from the PKI to the config directory and sets the <code>cert</code>, <code>key</code>, <code>ca</code> directives.
                  <span v-if="pkiCerts.length === 0 && !pkiCertsLoading" class="warn-text">No certs found — check PKI settings on the Easy-RSA page.</span>
                </span>
              </div>
              <div class="directive-field">
                <label class="directive-name">DH Parameters</label>
                <div style="display: flex; gap: 0.5rem; align-items: center; width: 100%">
                  <span class="dh-status">
                    <Tag :value="dhExists ? 'Available in PKI' : 'Not found in PKI'" :severity="dhExists ? 'success' : 'secondary'" />
                  </span>
                  <Button
                    label="Install"
                    icon="pi pi-download"
                    severity="info"
                    size="small"
                    :disabled="!dhExists"
                    :loading="installDhLoading"
                    @click="installDh"
                    style="white-space: nowrap"
                  />
                </div>
                <span class="directive-desc">Copies dh.pem from the PKI to the config directory and sets the <code>dh</code> directive.</span>
              </div>
            </div>
          </div>

          <!-- Inline blocks section -->
          <div class="category-section">
            <h3 class="category-title">Inline Blocks</h3>
            <div class="directive-grid">
              <div class="directive-field">
                <label class="directive-name">tls-auth (inline key)</label>
                <div style="display: flex; gap: 0.5rem; align-items: flex-start; width: 100%">
                  <Textarea
                    v-model="inlineBlocks['tls-auth']"
                    rows="6"
                    class="directive-input"
                    style="font-family: monospace; font-size: 0.8rem"
                    placeholder="-----BEGIN OpenVPN Static key V1-----&#10;...&#10;-----END OpenVPN Static key V1-----"
                  />
                  <Button label="Generate" icon="pi pi-key" severity="info" size="small" :loading="tlsKeyLoading" @click="generateTlsKey" style="white-space: nowrap" />
                </div>
                <span class="directive-desc">HMAC firewall key for tls-auth. Click Generate to create a new key on the server.</span>
              </div>
              <div class="directive-field">
                <label class="directive-name">tls-crypt (inline key)</label>
                <Textarea
                  v-model="inlineBlocks['tls-crypt']"
                  rows="6"
                  class="directive-input"
                  style="font-family: monospace; font-size: 0.8rem"
                  placeholder="-----BEGIN OpenVPN Static key V1-----&#10;...&#10;-----END OpenVPN Static key V1-----"
                />
                <span class="directive-desc">Encrypts the TLS control channel. Alternative to tls-auth (use one or the other).</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-msg">
          <p>No directive catalog loaded. <Button label="Load Config" size="small" @click="loadConfig" /></p>
        </div>
      </TabPanel>

      <!-- Raw Config Tab -->
      <TabPanel header="Raw Config">
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

          <Divider />
          <h3 class="settings-heading">CN / Username Enforcement</h3>
          <p class="settings-desc">
            When enabled, OpenVPN will call a verification script to ensure the client certificate's
            Common Name (CN) matches the username supplied at login. This prevents a user from
            authenticating with someone else's certificate.
          </p>

          <div class="field field-inline">
            <Checkbox v-model="settingsEnforceCn" :binary="true" input-id="enforce-cn" @change="saveSettings" />
            <label for="enforce-cn">Enforce CN = Username on this instance</label>
          </div>

          <div v-if="settingsEnforceCn" class="cn-deploy-section">
            <p class="settings-desc">
              Deploy the verification script to <code>/etc/openvpn/scripts/verify_cn_username.sh</code> on the server,
              then add the directives shown below to the server config (Config Editor tab).
            </p>
            <Button
              label="Deploy Script to Server"
              icon="pi pi-upload"
              severity="info"
              :loading="cnScriptDeploying"
              @click="deployCnScript"
            />
            <div v-if="cnScriptDeployed" class="cn-result">
              <Message severity="success" :closable="false">
                Script deployed to <code>{{ cnScriptPath }}</code>
              </Message>
              <p class="settings-desc" style="margin-top: 0.75rem">Add these directives to the server config:</p>
              <pre class="directives-box">{{ cnConfigDirectives }}</pre>
            </div>
          </div>
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
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Textarea from 'primevue/textarea'
import InputText from 'primevue/inputtext'
import Divider from 'primevue/divider'
import Message from 'primevue/message'
import { vpnInstancesApi } from '@/api/vpnInstances'
import type { VpnInstanceRead, VpnInstanceStatus, ServiceAction, DirectiveSpec } from '@/types'

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
const configSaving = ref(false)
const statusLoading = ref(false)
const actionLoading = ref<string | null>(null)
const settingsPamEnabled = ref(false)
const settingsEnforceCn = ref(false)
const settingsTlsAuthKey = ref('')
const settingsSaving = ref(false)
const tlsKeyLoading = ref(false)

const cnScriptDeploying = ref(false)
const cnScriptDeployed = ref(false)
const cnScriptPath = ref('')
const cnConfigDirectives = ref('')

// PKI integration
const pkiCerts = ref<string[]>([])
const pkiCertsLoading = ref(false)
const dhExists = ref(false)
const selectedCertCn = ref<string | null>(null)
const installCertLoading = ref(false)
const installDhLoading = ref(false)

const pkiCertOptions = computed(() =>
  pkiCerts.value.map((cn) => ({ label: cn, value: cn }))
)

// Directive catalog and form state
const directives = ref<DirectiveSpec[]>([])
const configForm = reactive<Record<string, unknown>>({})
const inlineBlocks = reactive<Record<string, string>>({})

const categoryLabels: Record<string, string> = {
  network: 'Network',
  crypto: 'Cryptography & TLS',
  auth: 'Authentication',
  logging: 'Logging & Management',
  connection: 'Connection Behaviour',
  security: 'Security & Privileges',
  process: 'Process',
}

const categories = computed(() => {
  const cats = new Set(directives.value.map((d) => d.category))
  const order = ['network', 'crypto', 'auth', 'logging', 'connection', 'security', 'process']
  return order.filter((c) => cats.has(c))
})

function directivesByCategory(cat: string): DirectiveSpec[] {
  return directives.value.filter((d) => d.category === cat && !d.deprecated)
}

function directiveOptions(d: DirectiveSpec) {
  return (d.allowed_values ?? []).map((v) => ({ label: v, value: v }))
}

// Returns the name of a conflicting directive if this one is blocked, or null if free to use.
function conflictingDirective(d: DirectiveSpec): string | null {
  for (const other of d.mutually_exclusive_with ?? []) {
    const val = configForm[other]
    const isSet =
      val !== undefined &&
      val !== null &&
      val !== '' &&
      val !== false &&
      !(Array.isArray(val) && (val as string[]).length === 0)
    if (isSet) return other
  }
  return null
}

function getMultiValues(name: string): string[] {
  const val = configForm[name]
  if (Array.isArray(val)) return val as string[]
  return []
}

function updateMultiValue(name: string, idx: number, value: string) {
  const arr = getMultiValues(name)
  arr[idx] = value
  configForm[name] = [...arr]
}

function addMultiValue(name: string) {
  const arr = getMultiValues(name)
  configForm[name] = [...arr, '']
}

function removeMultiValue(name: string, idx: number) {
  const arr = getMultiValues(name)
  arr.splice(idx, 1)
  configForm[name] = [...arr]
}

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
    settingsEnforceCn.value = instance.value.enforce_cn_username
    settingsTlsAuthKey.value = instance.value.tls_auth_key ?? ''
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load instance', life: 4000 })
  }
}

async function loadDirectives() {
  try {
    directives.value = await vpnInstancesApi.getDirectives()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to load directives catalog', life: 4000 })
  }
}

async function loadConfig() {
  configLoading.value = true
  try {
    const result = await vpnInstancesApi.getConfig(instanceId)
    configDirectives.value = result.directives

    // Populate form from server config
    // Reset form
    for (const key of Object.keys(configForm)) {
      delete configForm[key]
    }
    for (const key of Object.keys(inlineBlocks)) {
      delete inlineBlocks[key]
    }

    // Set values from loaded config
    for (const [key, value] of Object.entries(result.directives)) {
      configForm[key] = value
    }

    // Load inline blocks
    if (result.inline_blocks) {
      if (Array.isArray(result.inline_blocks)) {
        // Old format: just block names
      } else {
        for (const [key, value] of Object.entries(result.inline_blocks as Record<string, string>)) {
          inlineBlocks[key] = value
        }
      }
    }

    await loadPkiCerts()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load config', life: 4000 })
  } finally {
    configLoading.value = false
  }
}

async function saveConfig() {
  configSaving.value = true
  try {
    // Build directives from form, excluding empty values
    const dirData: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(configForm)) {
      if (value === null || value === undefined || value === '' || value === false) continue
      if (Array.isArray(value)) {
        const filtered = (value as string[]).filter((v) => v.trim() !== '')
        if (filtered.length > 0) dirData[key] = filtered
      } else {
        dirData[key] = value
      }
    }

    // Build inline blocks, excluding empty
    const blockData: Record<string, string> = {}
    for (const [key, value] of Object.entries(inlineBlocks)) {
      if (value && value.trim()) {
        blockData[key] = value.trim()
      }
    }

    await vpnInstancesApi.writeConfig(instanceId, {
      directives: dirData,
      inline_blocks: blockData,
    })
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Configuration saved to server.', life: 3000 })
    // Refresh raw view
    await loadConfig()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to save config', life: 4000 })
  } finally {
    configSaving.value = false
  }
}

async function generateTlsKey() {
  tlsKeyLoading.value = true
  try {
    const result = await vpnInstancesApi.generateTlsKey(instanceId)
    inlineBlocks['tls-auth'] = result.key
    settingsTlsAuthKey.value = result.key
    toast.add({ severity: 'success', summary: 'Generated', detail: 'TLS auth key generated.', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to generate TLS key', life: 4000 })
  } finally {
    tlsKeyLoading.value = false
  }
}

async function loadPkiCerts() {
  pkiCertsLoading.value = true
  try {
    const result = await vpnInstancesApi.listPkiCerts(instanceId)
    pkiCerts.value = result.issued_certs
    dhExists.value = result.dh_exists
  } catch (e) {
    // PKI may not be configured — silently ignore
  } finally {
    pkiCertsLoading.value = false
  }
}

async function installCert() {
  if (!selectedCertCn.value) return
  installCertLoading.value = true
  try {
    const result = await vpnInstancesApi.installCert(instanceId, selectedCertCn.value)
    // Update config form with installed paths
    configForm['cert'] = result.cert_path
    configForm['key'] = result.key_path
    configForm['ca'] = result.ca_path
    toast.add({ severity: 'success', summary: 'Installed', detail: `Certificate "${selectedCertCn.value}" installed. Save config to apply.`, life: 4000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to install certificate', life: 4000 })
  } finally {
    installCertLoading.value = false
  }
}

async function installDh() {
  installDhLoading.value = true
  try {
    const result = await vpnInstancesApi.installDh(instanceId)
    configForm['dh'] = result.dh_path
    toast.add({ severity: 'success', summary: 'Installed', detail: 'DH parameters installed. Save config to apply.', life: 4000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to install DH', life: 4000 })
  } finally {
    installDhLoading.value = false
  }
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    instance.value = await vpnInstancesApi.update(instanceId, {
      pam_enabled: settingsPamEnabled.value,
      enforce_cn_username: settingsEnforceCn.value,
      tls_auth_key: settingsTlsAuthKey.value || null,
    })
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Settings updated.', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to save settings', life: 4000 })
  } finally {
    settingsSaving.value = false
  }
}

async function deployCnScript() {
  cnScriptDeploying.value = true
  cnScriptDeployed.value = false
  try {
    const result = await vpnInstancesApi.deployCnVerifyScript(instanceId)
    cnScriptPath.value = result.script_path
    cnConfigDirectives.value = result.config_directives
    cnScriptDeployed.value = true
    toast.add({ severity: 'success', summary: 'Deployed', detail: `Script deployed to ${result.script_path}`, life: 4000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to deploy script', life: 4000 })
  } finally {
    cnScriptDeploying.value = false
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
  await Promise.all([loadInstance(), loadDirectives()])
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

/* Config editor styles */
.config-editor {
  max-width: 900px;
}
.category-section {
  margin-bottom: 2rem;
}
.category-title {
  margin: 0 0 1rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--p-primary-color);
  border-bottom: 2px solid var(--p-surface-200);
  padding-bottom: 0.5rem;
}
.directive-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.directive-field {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0.5rem;
  align-items: start;
}
.directive-field.directive-flag {
  grid-template-columns: auto auto 1fr;
  align-items: center;
}
.directive-field.directive-multi {
  grid-template-columns: 200px 1fr;
}
.directive-name {
  font-weight: 600;
  font-size: 0.875rem;
  padding-top: 0.4rem;
}
.directive-name.clickable {
  cursor: pointer;
  padding-top: 0;
}
.directive-input {
  width: 100%;
}
.directive-desc {
  grid-column: 1 / -1;
  font-size: 0.75rem;
  color: var(--p-surface-400);
  line-height: 1.4;
}
.multi-entries {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.multi-entry {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}
.multi-input {
  flex: 1;
}

/* Raw config styles */
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
.warn-text {
  color: var(--p-orange-500);
}
.directive-blocked {
  opacity: 0.55;
}
.input-with-conflict {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  width: 100%;
}
.conflict-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  color: var(--p-orange-500);
  font-weight: 600;
}
.conflict-badge .pi-ban {
  font-size: 0.75rem;
}
.dh-status {
  flex: 1;
}
.settings-desc {
  font-size: 0.875rem;
  color: var(--p-surface-600);
  margin: 0 0 0.75rem;
  line-height: 1.5;
}
.cn-deploy-section {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.cn-result {
  margin-top: 0.25rem;
}
.directives-box {
  background: var(--p-surface-900);
  color: var(--p-surface-100);
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.8rem;
  line-height: 1.6;
  white-space: pre;
  margin: 0;
}
</style>
