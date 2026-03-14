<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Users</h1>
      <div class="action-btns">
        <Button label="Add User" icon="pi pi-plus" @click="openAddDialog" />
      </div>
    </div>

    <DataTable :value="users" :loading="loading" striped-rows>
      <template #empty>No users found.</template>
      <Column field="username" header="Username" />
      <Column header="Role">
        <template #body="{ data }">
          <Tag :value="data.role" :severity="roleSeverity(data.role)" />
        </template>
      </Column>
      <Column header="Active">
        <template #body="{ data }">
          <Tag :value="data.is_active ? 'Active' : 'Inactive'" :severity="data.is_active ? 'success' : 'secondary'" />
        </template>
      </Column>
      <Column header="Superuser">
        <template #body="{ data }">
          <i v-if="data.is_superuser" class="pi pi-check text-success" />
          <span v-else class="text-muted">—</span>
        </template>
      </Column>
      <Column header="Actions" style="width: 10rem">
        <template #body="{ data }">
          <Button
            icon="pi pi-pencil"
            text
            rounded
            v-tooltip="'Edit'"
            @click="openEditDialog(data)"
          />
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            v-tooltip="'Delete'"
            :disabled="data.id === currentUser?.id"
            @click="confirmDelete(data)"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Add User Dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add User" modal style="width: 420px">
      <div class="field">
        <label>Username *</label>
        <InputText v-model="addForm.username" class="w-full" placeholder="min 3 characters" />
      </div>
      <div class="field">
        <label>Password *</label>
        <InputText v-model="addForm.password" type="password" class="w-full" placeholder="min 8 characters" />
      </div>
      <div class="field">
        <label>Role *</label>
        <Select
          v-model="addForm.role"
          :options="roleOptions"
          option-label="label"
          option-value="value"
          class="w-full"
        />
      </div>
      <div class="field field-inline">
        <Checkbox v-model="addForm.is_active" :binary="true" input-id="add-active" />
        <label for="add-active">Active</label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="addDialogVisible = false" />
        <Button label="Create" :loading="saving" @click="createUser" />
      </template>
    </Dialog>

    <!-- Edit User Dialog -->
    <Dialog v-model:visible="editDialogVisible" header="Edit User" modal style="width: 420px">
      <p class="text-muted" style="margin-bottom: 1rem">Editing: <strong>{{ editTarget?.username }}</strong></p>
      <div class="field">
        <label>New Password (leave blank to keep current)</label>
        <InputText v-model="editForm.password" type="password" class="w-full" placeholder="min 8 characters" />
      </div>
      <div class="field">
        <label>Role</label>
        <Select
          v-model="editForm.role"
          :options="roleOptions"
          option-label="label"
          option-value="value"
          class="w-full"
          :disabled="editTarget?.id === currentUser?.id"
        />
        <small v-if="editTarget?.id === currentUser?.id" class="text-muted">Cannot modify your own role</small>
      </div>
      <div class="field field-inline">
        <Checkbox v-model="editForm.is_active" :binary="true" input-id="edit-active" />
        <label for="edit-active">Active</label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editDialogVisible = false" />
        <Button label="Save" :loading="saving" @click="updateUser" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import { usersApi } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type { UserManagementRead } from '@/types'

const toast = useToast()
const confirm = useConfirm()
const authStore = useAuthStore()
const currentUser = authStore.currentUser

const users = ref<UserManagementRead[]>([])
const loading = ref(false)
const saving = ref(false)

const addDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editTarget = ref<UserManagementRead | null>(null)

const addForm = ref({
  username: '',
  password: '',
  role: 'viewer' as 'admin' | 'operator' | 'viewer',
  is_active: true,
})

const editForm = ref({
  password: '',
  role: 'viewer' as 'admin' | 'operator' | 'viewer',
  is_active: true,
})

const roleOptions = [
  { label: 'Admin', value: 'admin' },
  { label: 'Operator', value: 'operator' },
  { label: 'Viewer', value: 'viewer' },
]

function roleSeverity(role: string): string {
  if (role === 'admin') return 'danger'
  if (role === 'operator') return 'warn'
  return 'info'
}

async function loadUsers() {
  loading.value = true
  try {
    users.value = await usersApi.list()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to load users', life: 4000 })
  } finally {
    loading.value = false
  }
}

function openAddDialog() {
  addForm.value = { username: '', password: '', role: 'viewer', is_active: true }
  addDialogVisible.value = true
}

async function createUser() {
  if (!addForm.value.username || !addForm.value.password) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Username and password are required.', life: 3000 })
    return
  }
  saving.value = true
  try {
    await usersApi.create({
      username: addForm.value.username,
      password: addForm.value.password,
      role: addForm.value.role,
      is_active: addForm.value.is_active,
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

function openEditDialog(user: UserManagementRead) {
  editTarget.value = user
  editForm.value = {
    password: '',
    role: user.role as 'admin' | 'operator' | 'viewer',
    is_active: user.is_active,
  }
  editDialogVisible.value = true
}

async function updateUser() {
  if (!editTarget.value) return
  saving.value = true
  try {
    const payload: { password?: string; role?: 'admin' | 'operator' | 'viewer'; is_active?: boolean } = {
      is_active: editForm.value.is_active,
    }
    if (editForm.value.password) payload.password = editForm.value.password
    if (editTarget.value.id !== currentUser?.id) payload.role = editForm.value.role

    await usersApi.update(editTarget.value.id, payload)
    toast.add({ severity: 'success', summary: 'Updated', detail: 'User updated.', life: 3000 })
    editDialogVisible.value = false
    await loadUsers()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to update user', life: 4000 })
  } finally {
    saving.value = false
  }
}

function confirmDelete(user: UserManagementRead) {
  confirm.require({
    message: `Delete user "${user.username}"? This cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await usersApi.delete(user.id)
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'User deleted.', life: 3000 })
        await loadUsers()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Failed to delete user', life: 4000 })
      }
    },
  })
}

onMounted(loadUsers)
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
.action-btns {
  display: flex;
  gap: 0.5rem;
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
.text-muted {
  color: var(--p-surface-400);
}
.text-success {
  color: var(--p-green-500);
}
</style>
