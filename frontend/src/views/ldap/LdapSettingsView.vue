<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Active Directory / LDAP</h1>
      <Button label="Add Configuration" icon="pi pi-plus" @click="openAddDialog" />
    </div>

    <div v-if="configs.length === 0 && !loading" class="empty-state">
      <i class="pi pi-sitemap empty-icon" />
      <p>No LDAP configurations yet. Add one to enable Active Directory authentication.</p>
    </div>

    <div v-for="config in configs" :key="config.id" class="config-card">
      <div class="config-card-header">
        <div class="config-title-row">
          <h2 class="config-name">{{ config.name }}</h2>
          <Tag :value="config.is_active ? 'Active' : 'Inactive'" :severity="config.is_active ? 'success' : 'secondary'" />
        </div>
        <div class="config-meta">{{ config.server_url }} · {{ config.user_search_base }}</div>
        <div class="config-actions">
          <Button label="Test Connection" icon="pi pi-wifi" severity="info" size="small" :loading="testingId === config.id" @click="testConnection(config.id)" />
          <Button icon="pi pi-pencil" text rounded size="small" v-tooltip="'Edit'" @click="openEditDialog(config)" />
          <Button icon="pi pi-trash" severity="danger" text rounded size="small" v-tooltip="'Delete'" @click="confirmDelete(config)" />
        </div>
      </div>

      <!-- Group Role Mappings -->
      <div class="section">
        <h3 class="section-title">Group → Role Mappings</h3>
        <p class="section-desc">Map LDAP/AD group DNs to application roles. Users are assigned the highest-priority role from their group memberships.</p>
        <DataTable :value="mappings[config.id] ?? []" size="small">
          <template #empty>No mappings yet.</template>
          <Column field="group_dn" header="Group DN" />
          <Column header="Role">
            <template #body="{ data }">
              <Tag :value="data.role" :severity="roleSeverity(data.role)" />
            </template>
          </Column>
          <Column header="" style="width: 4rem">
            <template #body="{ data }">
              <Button icon="pi pi-trash" severity="danger" text rounded size="small" @click="deleteMapping(config.id, data.id)" />
            </template>
          </Column>
        </DataTable>
        <div class="add-mapping-row">
          <InputText v-model="newMapping[config.id].group_dn" placeholder="CN=VPN-Admins,OU=Groups,DC=example,DC=com" class="mapping-dn-input" />
          <Select
            v-model="newMapping[config.id].role"
            :options="roleOptions"
            option-label="label"
            option-value="value"
            placeholder="Role"
            style="width: 140px"
          />
          <Button label="Add" icon="pi pi-plus" size="small" @click="addMapping(config.id)" />
        </div>
      </div>
    </div>

    <!-- Test Connection Result -->
    <Dialog v-model:visible="testResultVisible" header="Connection Test" modal style="width: 440px">
      <Message :severity="testResult?.success ? 'success' : 'error'" :closable="false">
        {{ testResult?.message }}
      </Message>
      <template #footer>
        <Button label="Close" @click="testResultVisible = false" />
      </template>
    </Dialog>

    <!-- Add Config Dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add LDAP Configuration" modal style="width: 560px" :closable="!saving">
      <LdapConfigForm v-model="addForm" :is-create="true" />
      <template #footer>
        <Button label="Cancel" severity="secondary" :disabled="saving" @click="addDialogVisible = false" />
        <Button label="Create" :loading="saving" @click="createConfig" />
      </template>
    </Dialog>

    <!-- Edit Config Dialog -->
    <Dialog v-model:visible="editDialogVisible" header="Edit LDAP Configuration" modal style="width: 560px" :closable="!saving">
      <LdapConfigForm v-model="editForm" :is-create="false" />
      <template #footer>
        <Button label="Cancel" severity="secondary" :disabled="saving" @click="editDialogVisible = false" />
        <Button label="Save" :loading="saving" @click="updateConfig" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import LdapConfigForm from './LdapConfigForm.vue'
import { ldapApi } from '@/api/ldap'
import type { LdapConfigRead, LdapGroupRoleMappingRead, AppRole, LdapTestResult } from '@/types'

const toast = useToast()
const confirm = useConfirm()

const configs = ref<LdapConfigRead[]>([])
const mappings = reactive<Record<number, LdapGroupRoleMappingRead[]>>({})
const newMapping = reactive<Record<number, { group_dn: string; role: AppRole }>>({})
const loading = ref(false)
const saving = ref(false)
const testingId = ref<number | null>(null)
const testResultVisible = ref(false)
const testResult = ref<LdapTestResult | null>(null)

const addDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editTargetId = ref<number | null>(null)

function blankForm() {
  return {
    name: '',
    server_url: 'ldap://dc.example.com:389',
    server_url_backup: '',
    bind_dn: 'CN=svc-ovpn,OU=ServiceAccounts,DC=example,DC=com',
    bind_password: '',
    user_search_base: 'OU=Users,DC=example,DC=com',
    user_filter: '(objectClass=person)',
    username_attr: 'sAMAccountName',
    group_search_base: '',
    group_member_attr: 'member',
    use_tls: false,
    tls_verify_cert: true,
    ca_cert_pem: '',
    is_active: true,
  }
}

const addForm = ref(blankForm())
const editForm = ref(blankForm())

const roleOptions = [
  { label: 'Admin', value: 'admin' },
  { label: 'Operator', value: 'operator' },
  { label: 'Viewer', value: 'viewer' },
  { label: 'VPN User', value: 'vpn_user' },
]

function roleSeverity(role: string): string {
  if (role === 'admin') return 'danger'
  if (role === 'operator') return 'warn'
  if (role === 'vpn_user') return 'success'
  return 'info'
}

async function loadAll() {
  loading.value = true
  try {
    configs.value = await ldapApi.listConfigs()
    for (const cfg of configs.value) {
      mappings[cfg.id] = await ldapApi.listGroupMappings(cfg.id)
      if (!newMapping[cfg.id]) {
        newMapping[cfg.id] = { group_dn: '', role: 'vpn_user' }
      }
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load configs', life: 4000 })
  } finally {
    loading.value = false
  }
}

async function testConnection(id: number) {
  testingId.value = id
  try {
    testResult.value = await ldapApi.testConfig(id)
    testResultVisible.value = true
  } catch (e) {
    testResult.value = { success: false, message: (e as { detail?: string }).detail ?? 'Connection test failed' }
    testResultVisible.value = true
  } finally {
    testingId.value = null
  }
}

function openAddDialog() {
  addForm.value = blankForm()
  addDialogVisible.value = true
}

async function createConfig() {
  saving.value = true
  try {
    const created = await ldapApi.createConfig({
      ...addForm.value,
      server_url_backup: addForm.value.server_url_backup || undefined,
      group_search_base: addForm.value.group_search_base || undefined,
      ca_cert_pem: addForm.value.ca_cert_pem || undefined,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: 'LDAP configuration created.', life: 3000 })
    addDialogVisible.value = false
    mappings[created.id] = []
    newMapping[created.id] = { group_dn: '', role: 'vpn_user' }
    await loadAll()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to create config', life: 4000 })
  } finally {
    saving.value = false
  }
}

function openEditDialog(config: LdapConfigRead) {
  editTargetId.value = config.id
  editForm.value = {
    name: config.name,
    server_url: config.server_url,
    server_url_backup: config.server_url_backup ?? '',
    bind_dn: config.bind_dn,
    bind_password: '',
    user_search_base: config.user_search_base,
    user_filter: config.user_filter,
    username_attr: config.username_attr,
    group_search_base: config.group_search_base ?? '',
    group_member_attr: config.group_member_attr,
    use_tls: config.use_tls,
    tls_verify_cert: config.tls_verify_cert,
    ca_cert_pem: config.ca_cert_pem ?? '',
    is_active: config.is_active,
  }
  editDialogVisible.value = true
}

async function updateConfig() {
  if (!editTargetId.value) return
  saving.value = true
  try {
    const payload: Record<string, unknown> = { ...editForm.value }
    if (!payload.bind_password) delete payload.bind_password
    if (!payload.server_url_backup) payload.server_url_backup = null
    if (!payload.group_search_base) payload.group_search_base = null
    if (!payload.ca_cert_pem) payload.ca_cert_pem = null
    await ldapApi.updateConfig(editTargetId.value, payload)
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Configuration updated.', life: 3000 })
    editDialogVisible.value = false
    await loadAll()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to save config', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(config: LdapConfigRead) {
  confirm.require({
    message: `Delete LDAP config "${config.name}"? All group mappings will also be deleted.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await ldapApi.deleteConfig(config.id)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'Configuration deleted.', life: 3000 })
        await loadAll()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete', life: 4000 })
      }
    },
  })
}

async function addMapping(configId: number) {
  const m = newMapping[configId]
  if (!m.group_dn.trim()) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Group DN is required.', life: 3000 })
    return
  }
  try {
    await ldapApi.createGroupMapping(configId, { group_dn: m.group_dn.trim(), role: m.role })
    mappings[configId] = await ldapApi.listGroupMappings(configId)
    newMapping[configId] = { group_dn: '', role: 'vpn_user' }
    toast.add({ severity: 'success', summary: 'Added', detail: 'Mapping added.', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to add mapping', life: 4000 })
  }
}

async function deleteMapping(configId: number, mappingId: number) {
  try {
    await ldapApi.deleteGroupMapping(configId, mappingId)
    mappings[configId] = await ldapApi.listGroupMappings(configId)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete mapping', life: 4000 })
  }
}

onMounted(loadAll)
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
.config-card {
  background: var(--p-surface-0);
  border: 1px solid var(--p-surface-200);
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}
.config-card-header {
  margin-bottom: 1rem;
}
.config-title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.25rem;
}
.config-name {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
}
.config-meta {
  font-size: 0.8rem;
  color: var(--p-surface-400);
  margin-bottom: 0.75rem;
}
.config-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.section {
  border-top: 1px solid var(--p-surface-200);
  padding-top: 1rem;
  margin-top: 0.5rem;
}
.section-title {
  margin: 0 0 0.35rem;
  font-size: 0.9rem;
  font-weight: 700;
}
.section-desc {
  font-size: 0.8rem;
  color: var(--p-surface-400);
  margin: 0 0 0.75rem;
}
.add-mapping-row {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
  align-items: center;
}
.mapping-dn-input {
  flex: 1;
}
</style>
