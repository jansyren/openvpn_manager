import apiClient from './client'
import type {
  PamCopyRequest,
  PamCopyResult,
  PamGroupCreate,
  PamGroupRead,
  PamUserRead,
  StoredPamGroupRead,
  StoredPamUserRead,
} from '@/types'

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

  async updateUser(
    serverId: number,
    username: string,
    data: { password?: string; groups?: string[] },
  ): Promise<PamUserRead> {
    const response = await apiClient.put<PamUserRead>(`/pam/users/${serverId}/${username}`, data)
    return response.data
  },

  async deleteUser(serverId: number, username: string): Promise<void> {
    await apiClient.delete(`/pam/users/${serverId}/${username}`)
  },

  async listStoredUsers(serverId: number): Promise<StoredPamUserRead[]> {
    const response = await apiClient.get<StoredPamUserRead[]>(`/pam/users/${serverId}/stored`)
    return response.data
  },

  async listGroups(serverId: number): Promise<PamGroupRead[]> {
    const response = await apiClient.get<PamGroupRead[]>(`/pam/groups/${serverId}`)
    return response.data
  },

  async createGroup(serverId: number, data: PamGroupCreate): Promise<StoredPamGroupRead> {
    const response = await apiClient.post<StoredPamGroupRead>(`/pam/groups/${serverId}`, data)
    return response.data
  },

  async deleteGroup(serverId: number, name: string): Promise<void> {
    await apiClient.delete(`/pam/groups/${serverId}/${name}`)
  },

  async listStoredGroups(serverId: number): Promise<StoredPamGroupRead[]> {
    const response = await apiClient.get<StoredPamGroupRead[]>(`/pam/groups/${serverId}/stored`)
    return response.data
  },

  async copyUsers(data: PamCopyRequest): Promise<PamCopyResult> {
    const response = await apiClient.post<PamCopyResult>('/pam/copy', data)
    return response.data
  },
}
