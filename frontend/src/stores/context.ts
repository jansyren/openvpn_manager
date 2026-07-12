import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { vpnInstancesApi } from '@/api/vpnInstances'
import { useServersStore } from '@/stores/servers'
import type { VpnInstanceRead } from '@/types'

const KEY_SERVER = 'ctx_server_id'
const KEY_INSTANCE = 'ctx_instance_id'

function readStoredId(key: string): number | null {
  const v = localStorage.getItem(key)
  if (!v) return null
  const n = parseInt(v, 10)
  return isNaN(n) ? null : n
}

export const useContextStore = defineStore('context', () => {
  const serversStore = useServersStore()
  // Servers are owned by stores/servers.ts; read reactively from there instead of
  // keeping an independent copy, so server add/edit/delete elsewhere in the app is
  // reflected here immediately instead of only after a full page reload.
  const servers = computed(() => serversStore.servers)
  const instances = ref<VpnInstanceRead[]>([])
  const selectedServerId = ref<number | null>(readStoredId(KEY_SERVER))
  const selectedInstanceId = ref<number | null>(readStoredId(KEY_INSTANCE))

  watch(selectedServerId, (v) => {
    if (v !== null) localStorage.setItem(KEY_SERVER, String(v))
    else localStorage.removeItem(KEY_SERVER)
  })
  watch(selectedInstanceId, (v) => {
    if (v !== null) localStorage.setItem(KEY_INSTANCE, String(v))
    else localStorage.removeItem(KEY_INSTANCE)
  })

  const selectedServer = computed(() =>
    servers.value.find((s) => s.id === selectedServerId.value) ?? null,
  )
  const selectedInstance = computed(() =>
    instances.value.find((i) => i.id === selectedInstanceId.value) ?? null,
  )

  async function refreshInstances() {
    if (!selectedServerId.value) {
      instances.value = []
      return
    }
    try {
      instances.value = await vpnInstancesApi.list(selectedServerId.value)
    } catch {
      // non-fatal
    }
  }

  async function init() {
    try {
      await serversStore.fetchAll()
      if (selectedServerId.value && !servers.value.find((s) => s.id === selectedServerId.value)) {
        selectedServerId.value = null
        selectedInstanceId.value = null
      }
      if (selectedServerId.value) {
        await refreshInstances()
        if (
          selectedInstanceId.value &&
          !instances.value.find((i) => i.id === selectedInstanceId.value)
        ) {
          selectedInstanceId.value = null
        }
      }
    } catch {
      // non-fatal — selectors will be empty until next navigation
    }
  }

  async function setServer(id: number | null) {
    selectedServerId.value = id
    selectedInstanceId.value = null
    await refreshInstances()
  }

  function setInstance(id: number | null) {
    selectedInstanceId.value = id
  }

  return {
    servers,
    instances,
    selectedServerId,
    selectedInstanceId,
    selectedServer,
    selectedInstance,
    init,
    setServer,
    setInstance,
    refreshInstances,
  }
})
