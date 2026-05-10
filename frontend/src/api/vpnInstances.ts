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

  async getConfig(id: number): Promise<{ directives: Record<string, unknown>; inline_blocks: Record<string, string> }> {
    const response = await apiClient.get(`/vpn-instances/${id}/config`)
    return response.data
  },

  async writeConfig(id: number, data: { directives: Record<string, unknown>; inline_blocks?: Record<string, string>; validate?: boolean }): Promise<void> {
    await apiClient.put(`/vpn-instances/${id}/config`, data)
  },

  async generateTlsKey(id: number): Promise<{ key: string }> {
    const response = await apiClient.post<{ key: string }>(`/vpn-instances/${id}/generate-tls-key`)
    return response.data
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

  async listPkiCerts(id: number): Promise<{ issued_certs: string[]; dh_exists: boolean }> {
    const response = await apiClient.get(`/vpn-instances/${id}/pki-certs`)
    return response.data
  },

  async installCert(id: number, commonName: string): Promise<{ cert_path: string; key_path: string; ca_path: string }> {
    const response = await apiClient.post(`/vpn-instances/${id}/install-cert`, { common_name: commonName })
    return response.data
  },

  async installDh(id: number): Promise<{ dh_path: string }> {
    const response = await apiClient.post(`/vpn-instances/${id}/install-dh`)
    return response.data
  },

  async setCaPassphrase(id: number, passphrase: string | null): Promise<VpnInstanceRead> {
    const response = await apiClient.put<VpnInstanceRead>(`/vpn-instances/${id}/ca-passphrase`, {
      ca_passphrase: passphrase,
    })
    return response.data
  },

  async deployCnVerifyScript(id: number): Promise<{ script_path: string; config_directives: string }> {
    const response = await apiClient.post(`/vpn-instances/${id}/deploy-cn-verify-script`)
    return response.data
  },
}
