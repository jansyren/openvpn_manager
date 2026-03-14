import apiClient from './client'
import type { LoginRequest, TokenResponse, UserRead, ChangePasswordRequest } from '@/types'

export const authApi = {
  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/login', data)
    return response.data
  },

  async logout(): Promise<void> {
    await apiClient.post('/auth/logout')
  },

  async refresh(): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/refresh')
    return response.data
  },

  async me(): Promise<UserRead> {
    const response = await apiClient.get<UserRead>('/auth/me')
    return response.data
  },

  async changePassword(data: { current_password: string; new_password: string }): Promise<void> {
    await apiClient.put('/auth/me/password', data)
  },
}
