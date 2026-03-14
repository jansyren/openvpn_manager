<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">PAM User Manager</h1>
      <div class="action-btns">
        <Button label="Add User" icon="pi pi-plus" :disabled="!selectedServerId" @click="openAddDialog" />
      </div>
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
      <InputText
        v-model="groupFilter"
        placeholder="Group filter (e.g. openvpn)"
        class="filter-input"
        @keyup.enter="loadUsers"
      />
      <Button label="Filter" icon="pi pi-search" severity="secondary" :disabled="!selectedServerId" @click="loadUsers" />
    </div>

    <DataTable :value="users" :loading="loading" striped-rows>
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
      <Column header="Actions" style="width: 6rem">
        <template #body="{ data }">
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

    <!-- Add User Dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add PAM User" modal style="width: 440px">
      <div class="field">
        <label>Username *</label>
        <InputText v-model="form.username" class="w-full" placeholder="johndoe" />
      </div>
      <div class="field">
        <label>Password *</label>
        <InputText v-model="form.password" type="password" class="w-full" placeholder="Password" />
      </div>
      <div class="field">
        <label>Groups (comma-separated)</label>
        <InputText v-model="form.groupsRaw" class="w-full" placeholder="openvpn,users" />
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addDialogVisible = false" />
        <Button label="Create" :loading="saving" @click="createUser" />
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
import Message from 'primevue/message'
import { useServersStore } from '@/stores/servers'
import { pamApi } from '@/api/pam'
import type { PamUserRead } from '@/types'

const toast = useToast()
const confirm = useConfirm()
const serversStore = useServersStore()

const users = ref<PamUserRead[]>([])
const loading = ref(false)
const selectedServerId = ref<number | null>(null)
const groupFilter = ref('openvpn')
const addDialogVisible = ref(false)
const saving = ref(false)

const form = ref({
  username: '',
  password: '',
  groupsRaw: 'openvpn',
})

const serverOptions = computed(() =>
  serversStore.servers.map((s) => ({ label: s.name, value: s.id })),
)

async function onServerChange() {
  users.value = []
  if (selectedServerId.value) {
    await loadUsers()
  }
}

async function loadUsers() {
  if (!selectedServerId.value) return
  loading.value = true
  try {
    users.value = await pamApi.listUsers(selectedServerId.value, groupFilter.value || undefined)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load users', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  form.value = { username: '', password: '', groupsRaw: 'openvpn' }
  addDialogVisible.value = true
}

async function createUser() {
  if (!selectedServerId.value || !form.value.username || !form.value.password) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Username and password are required.', life: 3000 })
    return
  }
  saving.value = true
  try {
    const groups = form.value.groupsRaw
      .split(',')
      .map((g) => g.trim())
      .filter(Boolean)
    await pamApi.createUser(selectedServerId.value, {
      username: form.value.username,
      password: form.value.password,
      groups,
    })
    toast.add({ severity: 'success', summary: 'Created', detail: 'User created.', life: 3000 })
    addDialogVisible.value = false
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to create user', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(user: PamUserRead) {
  confirm.require({
    message: `Delete PAM user "${user.username}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await pamApi.deleteUser(selectedServerId.value!, user.username)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'User deleted.', life: 3000 })
        await loadUsers()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete', life: 4000 })
      }
    },
  })
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
.action-btns {
  display: flex;
  gap: 0.5rem;
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
.field {
  margin-bottom: 1rem;
}
.field label {
  display: block;
  margin-bottom: 0.35rem;
  font-weight: 600;
  font-size: 0.875rem;
}
.w-full {
  width: 100%;
}
.group-tag {
  margin-right: 0.3rem;
}
</style>
