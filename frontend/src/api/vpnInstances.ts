import apiClient from './client'
import type {
  VpnInstanceCreate,
  VpnInstanceRead,
  VpnInstanceStatus,
  DirectiveSpec,
  ServiceAction,
} from '@/types'

export const vpnInstancesApi = {
  async list(serverId?: number): Promise<VpnInstanceRead[]> {
    const params = serverId ? { server_id: serverId } : {}
    const response = await apiClient.get<VpnInstanceRead[]>('/vpn-instances', { params })
    return response.data
  },

  async get(id: number): Promise<VpnInstanceRead> {
    const response = await apiClient.get<VpnInstanceRead>(`/vpn-instances/${id}`)
    return response.data
  },

  async create(data: VpnInstanceCreate): Promise<VpnInstanceRead> {
    const response = await apiClient.post<VpnInstanceRead>('/vpn-instances', data)
    return response.data
  },

  async update(id: number, data: Partial<VpnInstanceCreate>): Promise<VpnInstanceRead> {
    const response = await apiClient.put<VpnInstanceRead>(`/vpn-instances/${id}`, data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/vpn-instances/${id}`)
  },

  async getConfig(id: number): Promise<{ directives: Record<string, unknown>; inline_blocks: string[] }> {
    const response = await apiClient.get(`/vpn-instances/${id}/config`)
    return response.data
  },

  async writeConfig(id: number, directives: Record<string, unknown>): Promise<void> {
    await apiClient.put(`/vpn-instances/${id}/config`, { directives })
  },

  async serviceAction(id: number, action: ServiceAction): Promise<unknown> {
    const response = await apiClient.post(`/vpn-instances/${id}/service`, { action })
    return response.data
  },

  async getStatus(id: number): Promise<VpnInstanceStatus> {
    const response = await apiClient.get<VpnInstanceStatus>(`/vpn-instances/${id}/status`)
    return response.data
  },

  async getLogs(id: number, lines = 100): Promise<{ logs: string }> {
    const response = await apiClient.get(`/vpn-instances/${id}/logs`, { params: { lines } })
    return response.data
  },

  async getDirectives(): Promise<DirectiveSpec[]> {
    const response = await apiClient.get<DirectiveSpec[]>('/vpn-instances/directives')
    return response.data
  },
}
