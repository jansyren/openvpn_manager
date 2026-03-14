<template>
  <div class="form-page">
    <h1 class="page-title">{{ isEdit ? 'Edit Server' : 'Add Server' }}</h1>

    <Card>
      <template #content>
        <form @submit.prevent="handleSubmit" novalidate>
          <div class="field">
            <label for="name">Server Name *</label>
            <InputText id="name" v-model="form.name" class="w-full" :class="{ 'p-invalid': errors.name }" />
            <small class="p-error">{{ errors.name }}</small>
          </div>

          <div class="field">
            <label for="description">Description</label>
            <Textarea id="description" v-model="form.description" class="w-full" rows="2" />
          </div>

          <div class="field-checkbox">
            <Checkbox id="is_local" v-model="form.is_local" binary />
            <label for="is_local">Local server (same machine as this application)</label>
          </div>

          <template v-if="!form.is_local">
            <div class="field">
              <label for="host">Host / IP Address *</label>
              <InputText id="host" v-model="form.host" class="w-full" :class="{ 'p-invalid': errors.host }" />
              <small class="p-error">{{ errors.host }}</small>
            </div>

            <div class="field">
              <label for="port">SSH Port</label>
              <InputNumber id="port" v-model="form.port" :min="1" :max="65535" class="w-full" />
            </div>

            <div class="field">
              <label for="ssh_username">SSH Username *</label>
              <InputText id="ssh_username" v-model="form.ssh_username" class="w-full" />
            </div>

            <div class="field">
              <label for="ssh_key">SSH Private Key (PEM) *</label>
              <Textarea
                id="ssh_key"
                v-model="form.ssh_private_key_pem"
                class="w-full"
                rows="6"
                placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;..."
                :class="{ 'p-invalid': errors.ssh_key }"
              />
              <small class="p-error">{{ errors.ssh_key }}</small>
            </div>
          </template>

          <div class="form-actions">
            <Button label="Cancel" severity="secondary" outlined @click="$router.back()" />
            <Button type="submit" :label="isEdit ? 'Update' : 'Create'" icon="pi pi-check" :loading="loading" />
          </div>
        </form>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'
import { useServersStore } from '@/stores/servers'
import { serversApi } from '@/api/servers'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const serversStore = useServersStore()

const isEdit = computed(() => !!route.params.id)
const loading = ref(false)
const form = ref({
  name: '',
  description: '',
  is_local: false,
  host: '',
  port: 22,
  ssh_username: '',
  ssh_private_key_pem: '',
})
const errors = ref<Record<string, string>>({})

onMounted(async () => {
  if (isEdit.value) {
    const server = await serversApi.get(Number(route.params.id))
    form.value.name = server.name
    form.value.description = server.description ?? ''
    form.value.is_local = server.is_local
    form.value.host = server.host ?? ''
    form.value.port = server.port
    form.value.ssh_username = server.ssh_username ?? ''
  }
})

function validate(): boolean {
  errors.value = {}
  if (!form.value.name) errors.value.name = 'Name is required'
  else if (!/^[a-zA-Z0-9_\-]+$/.test(form.value.name)) errors.value.name = 'Invalid characters in name'
  if (!form.value.is_local) {
    if (!form.value.host) errors.value.host = 'Host is required for remote servers'
    if (!isEdit.value && !form.value.ssh_private_key_pem) errors.value.ssh_key = 'SSH key is required'
  }
  return Object.keys(errors.value).length === 0
}

async function handleSubmit(): Promise<void> {
  if (!validate()) return
  loading.value = true
  try {
    const data = {
      name: form.value.name,
      description: form.value.description || undefined,
      is_local: form.value.is_local,
      host: form.value.is_local ? undefined : form.value.host,
      port: form.value.is_local ? undefined : form.value.port,
      ssh_username: form.value.is_local ? undefined : form.value.ssh_username,
      ssh_private_key_pem: form.value.is_local || !form.value.ssh_private_key_pem
        ? undefined
        : form.value.ssh_private_key_pem,
    }

    if (isEdit.value) {
      await serversStore.update(Number(route.params.id), data)
      toast.add({ severity: 'success', summary: 'Updated', detail: 'Server updated', life: 3000 })
    } else {
      await serversStore.create(data as Parameters<typeof serversStore.create>[0])
      toast.add({ severity: 'success', summary: 'Created', detail: 'Server added', life: 3000 })
    }
    router.push({ name: 'servers' })
  } catch (e: unknown) {
    toast.add({ severity: 'error', summary: 'Error', detail: (e as { detail?: string }).detail ?? 'Operation failed', life: 5000 })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.form-page { max-width: 640px; }
.page-title { margin: 0 0 1.5rem; font-size: 1.5rem; font-weight: 700; }
.field { margin-bottom: 1rem; }
.field label { display: block; font-size: 0.875rem; font-weight: 500; margin-bottom: 0.375rem; }
.field-checkbox { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; }
.form-actions { display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.5rem; }
</style>
