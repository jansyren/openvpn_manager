import apiClient from './client'
import type { VpnClientRead, VpnClientCreate } from '@/types'

export const clientsApi = {
  async list(vpnInstanceId?: number): Promise<VpnClientRead[]> {
    const params = vpnInstanceId ? { vpn_instance_id: vpnInstanceId } : {}
    const response = await apiClient.get<VpnClientRead[]>('/clients', { params })
    return response.data
  },

  async create(data: VpnClientCreate): Promise<VpnClientRead> {
    const response = await apiClient.post<VpnClientRead>('/clients', data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/clients/${id}`)
  },

  async revoke(id: number, caPassphrase?: string): Promise<void> {
    await apiClient.post(`/clients/${id}/revoke`, { ca_passphrase: caPassphrase ?? null })
  },

  async verifyPam(
    id: number,
    group = 'openvpn',
  ): Promise<{ pam_verified: boolean; username: string; group: string }> {
    const response = await apiClient.get(`/clients/${id}/verify-pam`, { params: { group } })
    return response.data
  },

  async downloadOvpn(id: number, filename: string): Promise<void> {
    const response = await apiClient.get(`/clients/${id}/ovpn`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([response.data], { type: 'application/x-openvpn-profile' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  },

  async previewOvpn(id: number): Promise<string> {
    const response = await apiClient.get(`/clients/${id}/ovpn`, { responseType: 'text' })
    return response.data
  },
}
