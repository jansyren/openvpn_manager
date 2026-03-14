<template>
  <div>
    <h1 class="page-title">Dashboard</h1>

    <div class="stats-grid">
      <Card>
        <template #title>Servers</template>
        <template #content>
          <span class="stat-number">{{ serversStore.servers.length }}</span>
        </template>
      </Card>
      <Card>
        <template #title>VPN Instances</template>
        <template #content>
          <span class="stat-number">{{ instanceCount }}</span>
        </template>
      </Card>
    </div>

    <div class="mt-4">
      <h2>Quick Actions</h2>
      <div class="action-buttons">
        <Button label="Manage Servers" icon="pi pi-server" @click="$router.push({ name: 'servers' })" />
        <Button label="VPN Instances" icon="pi pi-shield" severity="secondary" @click="$router.push({ name: 'vpn-instances' })" />
        <Button label="Backup" icon="pi pi-database" severity="secondary" @click="$router.push({ name: 'backup' })" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import { useServersStore } from '@/stores/servers'

const serversStore = useServersStore()
const instanceCount = ref(0)

onMounted(async () => {
  await serversStore.fetchAll()
})
</script>

<style scoped>
.page-title { margin: 0 0 1.5rem; font-size: 1.5rem; font-weight: 700; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
.stat-number { font-size: 2rem; font-weight: 700; color: var(--p-primary-500); }
.action-buttons { display: flex; gap: 0.75rem; flex-wrap: wrap; }
.mt-4 { margin-top: 2rem; }
</style>
