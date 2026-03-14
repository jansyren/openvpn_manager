import apiClient from './client'
import type { PamUserRead, PamGroupRead } from '@/types'

export const pamApi = {
  async listUsers(serverId: number, group = 'openvpn'): Promise<PamUserRead[]> {
    const response = await apiClient.get<PamUserRead[]>(`/pam/users/${serverId}`, {
      params: { group },
    })
    return response.data
  },

  async createUser(
    serverId: number,
    data: { username: string; password: string; groups: string[] },
  ): Promise<PamUserRead> {
    const response = await apiClient.post<PamUserRead>(`/pam/users/${serverId}`, data)
    return response.data
  },

  async deleteUser(serverId: number, username: string): Promise<void> {
    await apiClient.delete(`/pam/users/${serverId}/${username}`)
  },

  async listGroups(serverId: number): Promise<PamGroupRead[]> {
    const response = await apiClient.get<PamGroupRead[]>(`/pam/groups/${serverId}`)
    return response.data
  },
}
