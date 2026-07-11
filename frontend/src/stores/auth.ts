import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import { setAccessToken } from '@/api/client'
import type { UserRead } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // Access token stored in memory only (not localStorage) for security
  const accessToken = ref<string | null>(null)
  const currentUser = ref<UserRead | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isSuperuser = computed(() => currentUser.value?.is_superuser ?? false)
  const role = computed(() => currentUser.value?.role ?? null)
  const roles = computed(() => currentUser.value?.roles ?? [])
  const activeRole = computed(() => currentUser.value?.active_role ?? null)
  // "Admin-capable right now" — mirrors backend get_current_superuser's is_superuser-OR-admin-role check.
  const canAdminister = computed(() => isSuperuser.value || activeRole.value === 'admin')
  // Nav rendering reflects the CURRENTLY ACTIVE role, not just the DB-stored primary role.
  const isVpnUser = computed(() => activeRole.value === 'vpn_user')
  // Hard route lock-in: only when vpn_user is the user's ONLY resolved role (no switcher escape hatch).
  const isVpnUserOnly = computed(() => roles.value.length === 1 && roles.value[0] === 'vpn_user')

  async function login(username: string, password: string): Promise<void> {
    loading.value = true
    try {
      const tokenData = await authApi.login({ username, password })
      accessToken.value = tokenData.access_token
      setAccessToken(tokenData.access_token)
      currentUser.value = await authApi.me()
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      accessToken.value = null
      currentUser.value = null
      setAccessToken(null)
    }
  }

  async function tryRefresh(): Promise<boolean> {
    try {
      const tokenData = await authApi.refresh()
      accessToken.value = tokenData.access_token
      setAccessToken(tokenData.access_token)
      currentUser.value = await authApi.me()
      return true
    } catch {
      return false
    }
  }

  async function fetchMe(): Promise<void> {
    currentUser.value = await authApi.me()
  }

  async function switchRole(role: string): Promise<void> {
    loading.value = true
    try {
      const tokenData = await authApi.switchRole(role)
      accessToken.value = tokenData.access_token
      setAccessToken(tokenData.access_token)
      currentUser.value = await authApi.me()
    } finally {
      loading.value = false
    }
  }

  return {
    accessToken,
    currentUser,
    loading,
    isAuthenticated,
    isSuperuser,
    role,
    roles,
    activeRole,
    canAdminister,
    isVpnUser,
    isVpnUserOnly,
    login,
    logout,
    tryRefresh,
    fetchMe,
    switchRole,
  }
})
