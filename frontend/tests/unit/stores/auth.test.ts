import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import * as authApi from '@/api/auth'
import * as apiClient from '@/api/client'

// Mock the auth API
vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
    me: vi.fn(),
  },
}))

vi.mock('@/api/client', () => ({
  setAccessToken: vi.fn(),
  getAccessToken: vi.fn(() => null),
  default: {},
}))

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('is initially unauthenticated', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.currentUser).toBeNull()
  })

  it('sets access token and user on login', async () => {
    const mockUser = { id: 1, username: 'admin', is_active: true, is_superuser: true }
    vi.mocked(authApi.authApi.login).mockResolvedValue({
      access_token: 'test-token',
      token_type: 'bearer',
      expires_in: 900,
    })
    vi.mocked(authApi.authApi.me).mockResolvedValue(mockUser)

    const store = useAuthStore()
    await store.login('admin', 'Admin123!')

    expect(store.isAuthenticated).toBe(true)
    expect(store.currentUser?.username).toBe('admin')
    expect(store.isSuperuser).toBe(true)
    expect(apiClient.setAccessToken).toHaveBeenCalledWith('test-token')
  })

  it('clears state on logout', async () => {
    vi.mocked(authApi.authApi.logout).mockResolvedValue(undefined)

    const store = useAuthStore()
    store.accessToken = 'some-token'

    await store.logout()

    expect(store.isAuthenticated).toBe(false)
    expect(store.currentUser).toBeNull()
    expect(apiClient.setAccessToken).toHaveBeenCalledWith(null)
  })

  it('returns false from tryRefresh when refresh fails', async () => {
    vi.mocked(authApi.authApi.refresh).mockRejectedValue(new Error('No refresh token'))

    const store = useAuthStore()
    const result = await store.tryRefresh()

    expect(result).toBe(false)
    expect(store.isAuthenticated).toBe(false)
  })

  it('returns true from tryRefresh on success', async () => {
    const mockUser = { id: 1, username: 'admin', is_active: true, is_superuser: false }
    vi.mocked(authApi.authApi.refresh).mockResolvedValue({
      access_token: 'refreshed-token',
      token_type: 'bearer',
      expires_in: 900,
    })
    vi.mocked(authApi.authApi.me).mockResolvedValue(mockUser)

    const store = useAuthStore()
    const result = await store.tryRefresh()

    expect(result).toBe(true)
    expect(store.isAuthenticated).toBe(true)
  })

  it('marks non-superuser correctly', async () => {
    const mockUser = { id: 2, username: 'user', is_active: true, is_superuser: false }
    vi.mocked(authApi.authApi.login).mockResolvedValue({
      access_token: 'token',
      token_type: 'bearer',
      expires_in: 900,
    })
    vi.mocked(authApi.authApi.me).mockResolvedValue(mockUser)

    const store = useAuthStore()
    await store.login('user', 'User123!')
    expect(store.isSuperuser).toBe(false)
  })
})
