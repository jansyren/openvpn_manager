<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">Servers</h1>
      <Button
        v-if="authStore.isSuperuser"
        label="Add Server"
        icon="pi pi-plus"
        @click="$router.push({ name: 'servers-new' })"
      />
    </div>

    <DataTable
      :value="serversStore.servers"
      :loading="serversStore.loading"
      striped-rows
      show-gridlines
    >
      <Column field="name" header="Name" />
      <Column header="Type">
        <template #body="{ data }">
          <Tag :value="data.is_local ? 'Local' : 'Remote'" :severity="data.is_local ? 'info' : 'success'" />
        </template>
      </Column>
      <Column field="host" header="Host">
        <template #body="{ data }">{{ data.is_local ? 'localhost' : data.host }}</template>
      </Column>
      <Column header="Status">
        <template #body="{ data }">
          <Tag
            :value="data.ssh_host_fingerprint ? 'Verified' : 'Unverified'"
            :severity="data.ssh_host_fingerprint ? 'success' : 'warn'"
          />
        </template>
      </Column>
      <Column header="Actions">
        <template #body="{ data }">
          <div class="action-btns">
            <Button
              icon="pi pi-eye"
              size="small"
              severity="secondary"
              text
              @click="$router.push({ name: 'server-detail', params: { id: data.id } })"
            />
            <Button
              v-if="authStore.isSuperuser"
              icon="pi pi-pencil"
              size="small"
              severity="secondary"
              text
              @click="$router.push({ name: 'server-edit', params: { id: data.id } })"
            />
            <Button
              v-if="authStore.isSuperuser"
              icon="pi pi-trash"
              size="small"
              severity="danger"
              text
              @click="confirmDelete(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <ConfirmDialog />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { useServersStore } from '@/stores/servers'
import { useAuthStore } from '@/stores/auth'
import type { ServerRead } from '@/types'

const serversStore = useServersStore()
const authStore = useAuthStore()
const confirm = useConfirm()
const toast = useToast()

onMounted(() => serversStore.fetchAll())

function confirmDelete(server: ServerRead): void {
  confirm.require({
    message: `Delete server "${server.name}"? This will also delete all associated VPN instances and routes.`,
    header: 'Confirm Deletion',
    icon: 'pi pi-exclamation-triangle',
    severity: 'danger',
    accept: async () => {
      try {
        await serversStore.remove(server.id)
        toast.add({ severity: 'success', summary: 'Deleted', detail: `Server "${server.name}" deleted`, life: 3000 })
      } catch (e: unknown) {
        toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Delete failed', life: 5000 })
      }
    },
  })
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.page-title { margin: 0; font-size: 1.5rem; font-weight: 700; }
.action-btns { display: flex; gap: 0.25rem; }
</style>
