<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">PAM User Manager</h1>
    </div>

    <Message severity="info" :closable="false" class="pam-notice">
      PAM user management requires sudo configured on the target server.
    </Message>

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
    </div>

    <TabView>
      <!-- Users Tab -->
      <TabPanel header="Users">
        <div class="tab-toolbar">
          <div class="tab-toolbar-left">
            <InputText
              v-model="groupFilter"
              placeholder="Group filter (e.g. openvpn)"
              class="filter-input"
              @keyup.enter="loadUsers"
            />
            <Button label="Filter" icon="pi pi-search" severity="secondary" :disabled="!selectedServerId" @click="loadUsers" />
          </div>
          <Button label="Add User" icon="pi pi-plus" :disabled="!selectedServerId" @click="openAddUserDialog" />
        </div>

        <DataTable :value="users" :loading="usersLoading" striped-rows>
          <template #empty>No users found.</template>
          <Column field="username" header="Username" />
          <Column field="uid" header="UID">
            <template #body="{ data }">{{ data.uid ?? '—' }}</template>
          </Column>
          <Column header="Groups">
            <template #body="{ data }">
              <Tag v-for="g in data.groups" :key="g" :value="g" severity="secondary" class="group-tag" />
              <span v-if="!data.groups?.length">—</span>
            </template>
          </Column>
          <Column header="Stored">
            <template #body="{ data }">
              <Tag
                v-if="storedUserMap[data.username]"
                :value="storedUserMap[data.username].has_hash ? 'Stored ✓' : 'Stored (no hash)'"
                :severity="storedUserMap[data.username].has_hash ? 'success' : 'warn'"
              />
              <Tag v-else value="Not stored" severity="secondary" />
            </template>
          </Column>
          <Column header="Actions" style="width: 10rem">
            <template #body="{ data }">
              <Button
                v-tooltip.top="'Generate Certificate'"
                icon="pi pi-id-card"
                severity="info"
                text
                rounded
                class="mr-1"
                @click="openGenCertDialog(data)"
              />
              <Button
                icon="pi pi-trash"
                severity="danger"
                text
                rounded
                @click="confirmDeleteUser(data)"
              />
            </template>
          </Column>
        </DataTable>
      </TabPanel>

      <!-- Groups Tab -->
      <TabPanel header="Groups">
        <div class="tab-toolbar">
          <span />
          <Button label="Add Group" icon="pi pi-plus" :disabled="!selectedServerId" @click="openAddGroupDialog" />
        </div>

        <DataTable :value="storedGroups" :loading="groupsLoading" striped-rows>
          <template #empty>No groups stored. Create a group to track it here.</template>
          <Column field="name" header="Name" />
          <Column field="gid" header="GID">
            <template #body="{ data }">{{ data.gid ?? '—' }}</template>
          </Column>
          <Column header="Actions" style="width: 6rem">
            <template #body="{ data }">
              <Button
                icon="pi pi-trash"
                severity="danger"
                text
                rounded
                @click="confirmDeleteGroup(data)"
              />
            </template>
          </Column>
        </DataTable>
      </TabPanel>

      <!-- Copy Tab -->
      <TabPanel header="Copy to Server">
        <div class="copy-panel">
          <p class="copy-description">
            Copy all stored users and groups from the selected source server to another server.
            Users are recreated using their stored password hashes — no plaintext passwords needed.
          </p>

          <div class="field">
            <label>Target Server *</label>
            <Select
              v-model="targetServerId"
              :options="targetServerOptions"
              option-label="label"
              option-value="value"
              placeholder="Select target server"
              class="w-full"
            />
          </div>

          <div class="field field-checkbox">
            <Checkbox v-model="includeGroups" input-id="includeGroups" binary />
            <label for="includeGroups">Also copy groups</label>
          </div>

          <Button
            label="Copy Users"
            icon="pi pi-copy"
            :disabled="!selectedServerId || !targetServerId"
            :loading="copying"
            @click="copyToServer"
          />

          <div v-if="copyResult" class="copy-result">
            <Message
              :severity="copyResult.users_failed.length ? 'warn' : 'success'"
              :closable="false"
            >
              Users: {{ copyResult.users_created }} created,
              {{ copyResult.users_skipped }} skipped,
              {{ copyResult.users_failed.length }} failed.
              <span v-if="includeGroups">
                &nbsp;Groups: {{ copyResult.groups_created }} created,
                {{ copyResult.groups_skipped }} skipped,
                {{ copyResult.groups_failed.length }} failed.
              </span>
            </Message>
            <ul v-if="copyResult.users_failed.length || copyResult.groups_failed.length" class="failed-list">
              <li v-for="f in copyResult.groups_failed" :key="f" class="failed-item">Group: {{ f }}</li>
              <li v-for="f in copyResult.users_failed" :key="f" class="failed-item">User: {{ f }}</li>
            </ul>
          </div>
        </div>
      </TabPanel>
    </TabView>

    <!-- Add User Dialog -->
    <Dialog v-model:visible="addUserDialogVisible" header="Add PAM User" modal style="width: 440px">
      <div class="field">
        <label>Username *</label>
        <InputText v-model="userForm.username" class="w-full" placeholder="johndoe" />
      </div>
      <div class="field">
        <label>Password *</label>
        <InputText v-model="userForm.password" type="password" class="w-full" placeholder="Password" />
      </div>
      <div class="field">
        <label>Groups (comma-separated)</label>
        <InputText v-model="userForm.groupsRaw" class="w-full" placeholder="openvpn,users" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addUserDialogVisible = false" />
        <Button label="Create" :loading="userSaving" @click="createUser" />
      </template>
    </Dialog>

    <!-- Generate Certificate Dialog -->
    <Dialog v-model:visible="genCertDialogVisible" :header="`Generate Certificate — ${genCertUsername}`" modal style="width: 460px">
      <div class="field">
        <label>VPN Instance *</label>
        <Select
          v-model="genCertInstanceId"
          :options="vpnInstanceOptions"
          option-label="label"
          option-value="value"
          placeholder="Select VPN instance"
          class="w-full"
          @change="onGenCertInstanceChange"
        />
      </div>
      <div v-if="genCertInstanceId && !genCertInstanceHasPassphrase" class="field">
        <label>CA Passphrase *</label>
        <InputText v-model="genCertPassphrase" type="password" class="w-full" placeholder="Required — no passphrase stored for this instance" />
      </div>
      <Message v-if="genCertInstanceId && genCertInstanceHasPassphrase" severity="success" :closable="false" style="margin-top:0.5rem">
        This instance has a stored CA passphrase — no passphrase required.
      </Message>
      <div class="field" style="margin-top:0.75rem">
        <label>Certificate Expire Days</label>
        <InputNumber v-model="genCertExpireDays" class="w-full" :min="1" :max="9999" :use-grouping="false" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="genCertDialogVisible = false" />
        <Button label="Generate" icon="pi pi-id-card" :loading="genCertSaving" @click="generateCert" />
      </template>
    </Dialog>

    <!-- Add Group Dialog -->
    <Dialog v-model:visible="addGroupDialogVisible" header="Add PAM Group" modal style="width: 380px">
      <div class="field">
        <label>Group Name *</label>
        <InputText v-model="groupForm.name" class="w-full" placeholder="openvpn" />
      </div>
      <div class="field">
        <label>GID (optional)</label>
        <InputNumber v-model="groupForm.gid" class="w-full" placeholder="Leave blank for auto" :use-grouping="false" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addGroupDialogVisible = false" />
        <Button label="Create" :loading="groupSaving" @click="createGroup" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import { useServersStore } from '@/stores/servers'
import { pamApi } from '@/api/pam'
import { vpnInstancesApi } from '@/api/vpnInstances'
import { clientsApi } from '@/api/clients'
import type { PamUserRead, StoredPamGroupRead, StoredPamUserRead, PamCopyResult, VpnInstanceRead } from '@/types'

const toast = useToast()
const confirm = useConfirm()
const serversStore = useServersStore()

// ── Server selection ──────────────────────────────────────────────────────────
const selectedServerId = ref<number | null>(null)

const serverOptions = computed(() =>
  serversStore.servers.map((s) => ({ label: s.name, value: s.id })),
)

const targetServerOptions = computed(() =>
  serversStore.servers
    .filter((s) => s.id !== selectedServerId.value)
    .map((s) => ({ label: s.name, value: s.id })),
)

async function onServerChange() {
  users.value = []
  storedGroups.value = []
  copyResult.value = null
  if (selectedServerId.value) {
    await Promise.all([loadUsers(), loadStoredUsers(), loadStoredGroups()])
  }
}

// ── Users tab ─────────────────────────────────────────────────────────────────
const users = ref<PamUserRead[]>([])
const storedUsers = ref<StoredPamUserRead[]>([])
const usersLoading = ref(false)
const groupFilter = ref('openvpn')
const addUserDialogVisible = ref(false)
const userSaving = ref(false)

const userForm = ref({ username: '', password: '', groupsRaw: 'openvpn' })

const storedUserMap = computed(() => {
  const map: Record<string, StoredPamUserRead> = {}
  for (const u of storedUsers.value) {
    map[u.username] = u
  }
  return map
})

async function loadUsers() {
  if (!selectedServerId.value) return
  usersLoading.value = true
  try {
    users.value = await pamApi.listUsers(selectedServerId.value, groupFilter.value || undefined)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load users', life: 4000 })
  } finally {
    usersLoading.value = false
  }
}

async function loadStoredUsers() {
  if (!selectedServerId.value) return
  try {
    storedUsers.value = await pamApi.listStoredUsers(selectedServerId.value)
  } catch {
    // non-critical
  }
}

function openAddUserDialog() {
  userForm.value = { username: '', password: '', groupsRaw: 'openvpn' }
  addUserDialogVisible.value = true
}

async function createUser() {
  if (!selectedServerId.value || !userForm.value.username || !userForm.value.password) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Username and password are required.', life: 3000 })
    return
  }
  userSaving.value = true
  try {
    const groups = userForm.value.groupsRaw.split(',').map((g) => g.trim()).filter(Boolean)
    await pamApi.createUser(selectedServerId.value, {
      username: userForm.value.username,
      password: userForm.value.password,
      groups,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: 'User created.', life: 3000 })
    addUserDialogVisible.value = false
    await Promise.all([loadUsers(), loadStoredUsers()])
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to create user', life: 4000 })
  } finally {
    userSaving.value = false
  }
}

function confirmDeleteUser(user: PamUserRead) {
  confirm.require({
    message: `Delete PAM user "${user.username}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await pamApi.deleteUser(selectedServerId.value!, user.username)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'User deleted.', life: 3000 })
        await Promise.all([loadUsers(), loadStoredUsers()])
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete', life: 4000 })
      }
    },
  })
}

// ── Groups tab ────────────────────────────────────────────────────────────────
const storedGroups = ref<StoredPamGroupRead[]>([])
const groupsLoading = ref(false)
const addGroupDialogVisible = ref(false)
const groupSaving = ref(false)

const groupForm = ref<{ name: string; gid: number | null }>({ name: '', gid: null })

async function loadStoredGroups() {
  if (!selectedServerId.value) return
  groupsLoading.value = true
  try {
    storedGroups.value = await pamApi.listStoredGroups(selectedServerId.value)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load groups', life: 4000 })
  } finally {
    groupsLoading.value = false
  }
}

function openAddGroupDialog() {
  groupForm.value = { name: '', gid: null }
  addGroupDialogVisible.value = true
}

async function createGroup() {
  if (!selectedServerId.value || !groupForm.value.name) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Group name is required.', life: 3000 })
    return
  }
  groupSaving.value = true
  try {
    await pamApi.createGroup(selectedServerId.value, {
      name: groupForm.value.name,
      gid: groupForm.value.gid ?? undefined,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: 'Group created.', life: 3000 })
    addGroupDialogVisible.value = false
    await loadStoredGroups()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to create group', life: 4000 })
  } finally {
    groupSaving.value = false
  }
}

function confirmDeleteGroup(group: StoredPamGroupRead) {
  confirm.require({
    message: `Delete PAM group "${group.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await pamApi.deleteGroup(selectedServerId.value!, group.name)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'Group deleted.', life: 3000 })
        await loadStoredGroups()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete group', life: 4000 })
      }
    },
  })
}

// ── Generate Certificate ──────────────────────────────────────────────────────
const vpnInstances = ref<VpnInstanceRead[]>([])
const genCertDialogVisible = ref(false)
const genCertUsername = ref('')
const genCertInstanceId = ref<number | null>(null)
const genCertPassphrase = ref('')
const genCertExpireDays = ref(825)
const genCertSaving = ref(false)

const vpnInstanceOptions = computed(() =>
  vpnInstances.value.map((i) => ({ label: i.name, value: i.id })),
)

const genCertInstanceHasPassphrase = computed(() =>
  vpnInstances.value.find((i) => i.id === genCertInstanceId.value)?.has_ca_passphrase ?? false,
)

async function openGenCertDialog(user: PamUserRead) {
  genCertUsername.value = user.username
  genCertInstanceId.value = null
  genCertPassphrase.value = ''
  genCertExpireDays.value = 825
  // Load VPN instances for the selected server (and all instances if none match)
  try {
    vpnInstances.value = selectedServerId.value
      ? await vpnInstancesApi.list(selectedServerId.value)
      : await vpnInstancesApi.list()
  } catch {
    vpnInstances.value = []
  }
  genCertDialogVisible.value = true
}

function onGenCertInstanceChange() {
  genCertPassphrase.value = ''
}

async function generateCert() {
  if (!genCertInstanceId.value) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Select a VPN instance.', life: 3000 })
    return
  }
  if (!genCertInstanceHasPassphrase.value && !genCertPassphrase.value) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'CA passphrase is required.', life: 3000 })
    return
  }
  genCertSaving.value = true
  try {
    await clientsApi.create({
      vpn_instance_id: genCertInstanceId.value,
      name: genCertUsername.value,
      client_type: 'user',
      import_existing: false,
      ca_passphrase: genCertPassphrase.value || undefined,
      cert_expire_days: genCertExpireDays.value,
    })
    toast.add({ severity: 'success', summary: 'Certificate generated', detail: `Certificate created for ${genCertUsername.value}.`, life: 4000 })
    genCertDialogVisible.value = false
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to generate certificate', life: 5000 })
  } finally {
    genCertSaving.value = false
  }
}

// ── Copy tab ──────────────────────────────────────────────────────────────────
const targetServerId = ref<number | null>(null)
const includeGroups = ref(true)
const copying = ref(false)
const copyResult = ref<PamCopyResult | null>(null)

async function copyToServer() {
  if (!selectedServerId.value || !targetServerId.value) return
  copying.value = true
  copyResult.value = null
  try {
    copyResult.value = await pamApi.copyUsers({
      source_server_id: selectedServerId.value,
      target_server_id: targetServerId.value,
      include_groups: includeGroups.value,
    })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Copy failed', life: 4000 })
  } finally {
    copying.value = false
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
  margin-bottom: 1rem;
}
.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
}
.pam-notice {
  margin-bottom: 1rem;
}
.filter-bar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.filter-select {
  min-width: 220px;
}
.filter-input {
  min-width: 200px;
}
.tab-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  gap: 0.75rem;
}
.tab-toolbar-left {
  display: flex;
  gap: 0.75rem;
  align-items: center;
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
.field-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.field-checkbox label {
  margin-bottom: 0;
}
.w-full {
  width: 100%;
}
.group-tag {
  margin-right: 0.3rem;
}
.copy-panel {
  max-width: 500px;
  padding: 0.5rem 0;
}
.copy-description {
  color: var(--p-text-muted-color, #6c757d);
  margin-bottom: 1.25rem;
  font-size: 0.9rem;
}
.copy-result {
  margin-top: 1rem;
}
.failed-list {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
  font-size: 0.875rem;
}
.failed-item {
  color: var(--p-red-500, #ef4444);
}
</style>
