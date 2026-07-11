<template>
  <div class="role-switcher">
    <i class="pi pi-user-edit role-icon" />
    <Select
      :model-value="authStore.activeRole"
      :options="roleOptions"
      option-label="label"
      option-value="value"
      class="role-select"
      @update:model-value="handleChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Select from 'primevue/select'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const roleOptions = computed(() =>
  authStore.roles.map((r) => ({ label: r, value: r })),
)

async function handleChange(newRole: string): Promise<void> {
  await authStore.switchRole(newRole)
  if (newRole === 'vpn_user' && route.name !== 'my-vpn') {
    router.push({ name: 'my-vpn' })
  } else if (newRole !== 'vpn_user' && route.name === 'my-vpn') {
    router.push({ name: 'dashboard' })
  }
}
</script>

<style scoped>
.role-switcher {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 0;
  border-top: 1px solid var(--p-surface-700);
}

.role-icon {
  color: var(--p-surface-300);
  font-size: 0.9rem;
}

.role-select {
  flex: 1;
  min-width: 0;
}
</style>
