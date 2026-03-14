import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      component: () => import('@/layouts/DefaultLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
        },
        // Servers
        {
          path: 'servers',
          name: 'servers',
          component: () => import('@/views/servers/ServerListView.vue'),
        },
        {
          path: 'servers/new',
          name: 'servers-new',
          component: () => import('@/views/servers/ServerFormView.vue'),
          meta: { requiresSuperuser: true },
        },
        {
          path: 'servers/:id',
          name: 'server-detail',
          component: () => import('@/views/servers/ServerDetailView.vue'),
        },
        {
          path: 'servers/:id/edit',
          name: 'server-edit',
          component: () => import('@/views/servers/ServerFormView.vue'),
          meta: { requiresSuperuser: true },
        },
        // VPN Instances
        {
          path: 'vpn',
          name: 'vpn-instances',
          component: () => import('@/views/vpn/VpnInstanceListView.vue'),
        },
        {
          path: 'vpn/:id',
          name: 'vpn-instance-detail',
          component: () => import('@/views/vpn/VpnInstanceDetailView.vue'),
        },
        // Routes
        {
          path: 'routes',
          name: 'routes',
          component: () => import('@/views/routes/RouteManagerView.vue'),
        },
        // Clients
        {
          path: 'clients',
          name: 'clients',
          component: () => import('@/views/clients/ClientListView.vue'),
        },
        // Certificates
        {
          path: 'certificates',
          name: 'certificates',
          component: () => import('@/views/certificates/CertificateManagerView.vue'),
        },
        // PAM
        {
          path: 'pam',
          name: 'pam',
          component: () => import('@/views/pam/PamUserManagerView.vue'),
          meta: { requiresSuperuser: true },
        },
        // Easy-RSA
        {
          path: 'easyrsa',
          name: 'easyrsa',
          component: () => import('@/views/easyrsa/EasyRsaSettingsView.vue'),
          meta: { requiresSuperuser: true },
        },
        // Backup
        {
          path: 'backup',
          name: 'backup',
          component: () => import('@/views/backup/BackupRestoreView.vue'),
        },
        // Deploy
        {
          path: 'deploy',
          name: 'deploy',
          component: () => import('@/views/deploy/DeploymentView.vue'),
          meta: { requiresSuperuser: true },
        },
        // Users
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/users/UserListView.vue'),
          meta: { requiresSuperuser: true },
        },
      ],
    },
    // Catch-all
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// Navigation guard
router.beforeEach(async (to) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth === false) return true

  // Try to restore session via refresh token cookie on first load
  if (!authStore.isAuthenticated) {
    const refreshed = await authStore.tryRefresh()
    if (!refreshed) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  if (to.meta.requiresSuperuser && !authStore.isSuperuser) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
