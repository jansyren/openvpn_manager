<template>
  <div class="layout-wrapper">
    <nav class="sidebar">
      <div class="sidebar-header">
        <span class="logo">OpenVPN Manager</span>
      </div>
      <ul class="nav-menu">
        <!-- vpn_user sees only their VPN portal -->
        <template v-if="authStore.isVpnUser">
          <li><RouterLink :to="{ name: 'my-vpn' }"><i class="pi pi-download" /> My VPN Config</RouterLink></li>
        </template>
        <!-- all other roles see full nav -->
        <template v-else>
          <li><RouterLink :to="{ name: 'dashboard' }"><i class="pi pi-home" /> Dashboard</RouterLink></li>
          <li><RouterLink :to="{ name: 'servers' }"><i class="pi pi-server" /> Servers</RouterLink></li>
          <li><RouterLink :to="{ name: 'vpn-instances' }"><i class="pi pi-shield" /> VPN Instances</RouterLink></li>
          <li><RouterLink :to="{ name: 'routes' }"><i class="pi pi-directions" /> Routes</RouterLink></li>
          <li><RouterLink :to="{ name: 'clients' }"><i class="pi pi-users" /> Clients</RouterLink></li>
          <li><RouterLink :to="{ name: 'certificates' }"><i class="pi pi-verified" /> Certificates</RouterLink></li>
          <li v-if="authStore.canAdminister">
            <RouterLink :to="{ name: 'pam' }"><i class="pi pi-key" /> PAM Users</RouterLink>
          </li>
          <li v-if="authStore.canAdminister">
            <RouterLink :to="{ name: 'easyrsa' }"><i class="pi pi-lock" /> Easy-RSA</RouterLink>
          </li>
          <li><RouterLink :to="{ name: 'backup' }"><i class="pi pi-database" /> Backup</RouterLink></li>
          <li v-if="authStore.canAdminister">
            <RouterLink :to="{ name: 'deploy' }"><i class="pi pi-cloud-upload" /> Deploy</RouterLink>
          </li>
          <li v-if="authStore.canOperate">
            <RouterLink :to="{ name: 'users' }"><i class="pi pi-users" /> Users</RouterLink>
          </li>
          <li v-if="authStore.canAdminister">
            <RouterLink :to="{ name: 'ldap' }"><i class="pi pi-sitemap" /> Active Directory</RouterLink>
          </li>
        </template>
      </ul>
      <RoleSwitcher v-if="authStore.roles.length > 1" />
      <div class="sidebar-footer">
        <span class="username">{{ authStore.currentUser?.username }}</span>
        <Button icon="pi pi-sign-out" severity="secondary" text @click="handleLogout" />
      </div>
    </nav>

    <div class="content-area">
      <div v-if="showContextBar" class="context-bar">
        <i class="pi pi-server ctx-icon" />
        <Select
          :model-value="ctx.selectedServerId"
          :options="serverOptions"
          option-label="label"
          option-value="value"
          placeholder="Select Server"
          show-clear
          class="ctx-select"
          @update:model-value="handleServerChange"
        />
        <i class="pi pi-shield ctx-icon" />
        <Select
          :model-value="ctx.selectedInstanceId"
          :options="instanceOptions"
          option-label="label"
          option-value="value"
          placeholder="Select VPN Instance"
          show-clear
          :disabled="!ctx.selectedServerId || ctx.instances.length === 0"
          class="ctx-select"
          @update:model-value="ctx.setInstance"
        />
        <span v-if="ctx.selectedServer" class="ctx-hint">
          {{ ctx.selectedServer.is_local ? 'Local' : ctx.selectedServer.host }}
        </span>
      </div>

      <main class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import Select from 'primevue/select'
import RoleSwitcher from '@/components/RoleSwitcher.vue'
import { useAuthStore } from '@/stores/auth'
import { useContextStore } from '@/stores/context'

const authStore = useAuthStore()
const ctx = useContextStore()
const router = useRouter()
const route = useRoute()

const CONTEXT_BAR_EXCLUDED: string[] = [
  'servers',
  'servers-new',
  'server-detail',
  'server-edit',
  'vpn-instances',
  'vpn-instance-detail',
]

const showContextBar = computed(() => {
  const name = route.name as string | undefined
  return !!name && !CONTEXT_BAR_EXCLUDED.includes(name)
})

const serverOptions = computed(() =>
  ctx.servers.map((s) => ({ label: s.name, value: s.id })),
)

const instanceOptions = computed(() =>
  ctx.instances.map((i) => ({ label: i.name, value: i.id })),
)

async function handleServerChange(id: number | null) {
  await ctx.setServer(id)
}

async function handleLogout(): Promise<void> {
  await authStore.logout()
  router.push({ name: 'login' })
}

onMounted(async () => {
  await ctx.init()
})
</script>

<style scoped>
.layout-wrapper {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 240px;
  background: var(--p-surface-900);
  color: var(--p-surface-0);
  display: flex;
  flex-direction: column;
  padding: 1rem;
  overflow-y: auto;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 0.5rem 0 1.5rem;
}

.logo {
  font-size: 1.1rem;
  font-weight: 700;
}

.nav-menu {
  list-style: none;
  padding: 0;
  margin: 0;
  flex: 1;
}

.nav-menu li {
  margin-bottom: 0.25rem;
}

.nav-menu a {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  color: var(--p-surface-200);
  text-decoration: none;
  font-size: 0.875rem;
  transition: background 0.15s;
}

.nav-menu a:hover,
.nav-menu a.router-link-active {
  background: var(--p-surface-700);
  color: var(--p-surface-0);
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 1rem;
  border-top: 1px solid var(--p-surface-700);
}

.username {
  font-size: 0.8rem;
  color: var(--p-surface-300);
}

/* ── Content area ───────────────────────────────────────────── */
.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.context-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1.5rem;
  background: var(--p-surface-0);
  border-bottom: 1px solid var(--p-surface-200);
  flex-shrink: 0;
}

.ctx-icon {
  color: var(--p-surface-400);
  font-size: 0.9rem;
}

.ctx-select {
  min-width: 200px;
}

.ctx-hint {
  font-size: 0.8rem;
  color: var(--p-surface-400);
  margin-left: auto;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  background: var(--p-surface-50);
}
</style>
