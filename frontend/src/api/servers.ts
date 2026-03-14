import apiClient from './client'
import type { ServerCreate, ServerRead, ServerTestConnectionResult, DiscoveredConfig } from '@/types'

export const serversApi = {
  async list(): Promise<ServerRead[]> {
    const response = await apiClient.get<ServerRead[]>('/servers')
    return response.data
  },

  async get(id: number): Promise<ServerRead> {
    const response = await apiClient.get<ServerRead>(`/servers/${id}`)
    return response.data
  },

  async create(data: ServerCreate): Promise<ServerRead> {
    const response = await apiClient.post<ServerRead>('/servers', data)
    return response.data
  },

  async update(id: number, data: Partial<ServerCreate>): Promise<ServerRead> {
    const response = await apiClient.put<ServerRead>(`/servers/${id}`, data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/servers/${id}`)
  },

  async testConnection(id: number): Promise<ServerTestConnectionResult> {
    const response = await apiClient.post<ServerTestConnectionResult>(`/servers/${id}/test-connection`)
    return response.data
  },

  async discover(id: number): Promise<DiscoveredConfig[]> {
    const response = await apiClient.post<DiscoveredConfig[]>(`/servers/${id}/discover`)
    return response.data
  },
}
