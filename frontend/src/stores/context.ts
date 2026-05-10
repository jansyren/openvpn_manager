import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { serversApi } from '@/api/servers'
import { vpnInstancesApi } from '@/api/vpnInstances'
import type { ServerRead, VpnInstanceRead } from '@/types'

const KEY_SERVER = 'ctx_server_id'
const KEY_INSTANCE = 'ctx_instance_id'

function readStoredId(key: string): number | null {
  const v = localStorage.getItem(key)
  if (!v) return null
  const n = parseInt(v, 10)
  return isNaN(n) ? null : n
}

export const useContextStore = defineStore('context', () => {
  const servers = ref<ServerRead[]>([])
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

  async function init() {
    try {
      servers.value = await serversApi.list()
      if (selectedServerId.value && !servers.value.find((s) => s.id === selectedServerId.value)) {
        selectedServerId.value = null
        selectedInstanceId.value = null
      }
      if (selectedServerId.value) {
        instances.value = await vpnInstancesApi.list(selectedServerId.value)
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
    instances.value = []
    if (id) {
      try {
        instances.value = await vpnInstancesApi.list(id)
      } catch {
        // non-fatal
      }
    }
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
  }
})
