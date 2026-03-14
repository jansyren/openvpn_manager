import apiClient from './client'
import type { RouteRead, RouteCreate, LiveRoutingTable } from '@/types'

export const routesApi = {
  async list(serverId?: number): Promise<RouteRead[]> {
    const params = serverId ? { server_id: serverId } : {}
    const response = await apiClient.get<RouteRead[]>('/routes', { params })
    return response.data
  },

  async create(data: RouteCreate): Promise<RouteRead> {
    const response = await apiClient.post<RouteRead>('/routes', data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/routes/${id}`)
  },

  async apply(id: number): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>(`/routes/${id}/apply`)
    return response.data
  },

  async remove(id: number): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>(`/routes/${id}/remove`)
    return response.data
  },

  async getLive(serverId: number): Promise<LiveRoutingTable> {
    const response = await apiClient.get<LiveRoutingTable>(`/routes/live/${serverId}`)
    return response.data
  },
}
