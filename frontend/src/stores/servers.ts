import { defineStore } from 'pinia'
import { ref } from 'vue'
import { serversApi } from '@/api/servers'
import type { ServerRead, ServerCreate } from '@/types'

export const useServersStore = defineStore('servers', () => {
  const servers = ref<ServerRead[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      servers.value = await serversApi.list()
    } catch (e: unknown) {
      error.value = (e as { detail?: string }).detail ?? 'Failed to load servers'
    } finally {
      loading.value = false
    }
  }

  async function create(data: ServerCreate): Promise<ServerRead> {
    const server = await serversApi.create(data)
    servers.value.push(server)
    return server
  }

  async function update(id: number, data: Partial<ServerCreate>): Promise<ServerRead> {
    const updated = await serversApi.update(id, data)
    const idx = servers.value.findIndex((s) => s.id === id)
    if (idx !== -1) servers.value[idx] = updated
    return updated
  }

  async function remove(id: number): Promise<void> {
    await serversApi.delete(id)
    servers.value = servers.value.filter((s) => s.id !== id)
  }

  const fetchServers = fetchAll

  return { servers, loading, error, fetchAll, fetchServers, create, update, remove }
})
