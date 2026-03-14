<template>
  <div class="layout-wrapper">
    <nav class="sidebar">
      <div class="sidebar-header">
        <span class="logo">OpenVPN Manager</span>
      </div>
      <ul class="nav-menu">
        <li><RouterLink :to="{ name: 'dashboard' }"><i class="pi pi-home" /> Dashboard</RouterLink></li>
        <li><RouterLink :to="{ name: 'servers' }"><i class="pi pi-server" /> Servers</RouterLink></li>
        <li><RouterLink :to="{ name: 'vpn-instances' }"><i class="pi pi-shield" /> VPN Instances</RouterLink></li>
        <li><RouterLink :to="{ name: 'routes' }"><i class="pi pi-directions" /> Routes</RouterLink></li>
        <li><RouterLink :to="{ name: 'clients' }"><i class="pi pi-users" /> Clients</RouterLink></li>
        <li><RouterLink :to="{ name: 'certificates' }"><i class="pi pi-verified" /> Certificates</RouterLink></li>
        <li v-if="authStore.isSuperuser">
          <RouterLink :to="{ name: 'pam' }"><i class="pi pi-key" /> PAM Users</RouterLink>
        </li>
        <li v-if="authStore.isSuperuser">
          <RouterLink :to="{ name: 'easyrsa' }"><i class="pi pi-lock" /> Easy-RSA</RouterLink>
        </li>
        <li><RouterLink :to="{ name: 'backup' }"><i class="pi pi-database" /> Backup</RouterLink></li>
        <li v-if="authStore.isSuperuser">
          <RouterLink :to="{ name: 'deploy' }"><i class="pi pi-cloud-upload" /> Deploy</RouterLink>
        </li>
        <li v-if="authStore.isSuperuser">
          <RouterLink :to="{ name: 'users' }"><i class="pi pi-users" /> Users</RouterLink>
        </li>
      </ul>
      <div class="sidebar-footer">
        <span class="username">{{ authStore.currentUser?.username }}</span>
        <Button icon="pi pi-sign-out" severity="secondary" text @click="handleLogout" />
      </div>
    </nav>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'

const authStore = useAuthStore()
const router = useRouter()

async function handleLogout(): Promise<void> {
  await authStore.logout()
  router.push({ name: 'login' })
}
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

.content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  background: var(--p-surface-50);
}
</style>
