import apiClient from './client'
import type { EasyRsaSettings } from '@/types'

interface ServerLevelParams {
  easyrsa_path: string
  pki_dir: string
  use_sudo: boolean
}

export const easyrsaApi = {
  // ── VPN instance-level endpoints ──────────────────────────────────────
  async getSettings(vpnInstanceId: number): Promise<EasyRsaSettings> {
    const response = await apiClient.get<EasyRsaSettings>(`/easyrsa/${vpnInstanceId}/settings`)
    return response.data
  },

  async updatePath(vpnInstanceId: number, easyrsaPath: string): Promise<void> {
    await apiClient.put(`/easyrsa/${vpnInstanceId}/path`, { easyrsa_path: easyrsaPath })
  },

  async updatePkiDir(vpnInstanceId: number, pkiDir: string): Promise<void> {
    await apiClient.put(`/easyrsa/${vpnInstanceId}/pki-dir`, { pki_dir: pkiDir })
  },

  async updateSudo(vpnInstanceId: number, easyrsa_use_sudo: boolean): Promise<void> {
    await apiClient.put(`/easyrsa/${vpnInstanceId}/sudo`, { easyrsa_use_sudo })
  },

  async updateServer(vpnInstanceId: number, easyrsaServerId: number | null): Promise<void> {
    await apiClient.put(`/easyrsa/${vpnInstanceId}/server`, { easyrsa_server_id: easyrsaServerId })
  },

  async initPki(vpnInstanceId: number, force = false): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/${vpnInstanceId}/init-pki`, { force })
    return response.data
  },

  async buildCa(
    vpnInstanceId: number,
    data: { common_name: string; passphrase?: string; expire_days?: number },
  ): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/${vpnInstanceId}/build-ca`, data)
    return response.data
  },

  async buildServer(
    vpnInstanceId: number,
    data: { common_name: string; passphrase?: string; expire_days?: number },
  ): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/${vpnInstanceId}/build-server`, data)
    return response.data
  },

  async genDh(vpnInstanceId: number): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/${vpnInstanceId}/gen-dh`)
    return response.data
  },

  async pkiStatus(vpnInstanceId: number): Promise<{ pki_initialized: boolean; ca_built: boolean }> {
    const response = await apiClient.get(`/easyrsa/${vpnInstanceId}/pki-status`)
    return response.data
  },

  async renewCa(
    vpnInstanceId: number,
    data: { ca_passphrase: string; expire_days?: number },
  ): Promise<{ message: string }> {
    const response = await apiClient.post(`/easyrsa/${vpnInstanceId}/renew-ca`, data)
    return response.data
  },

  async crossSign(
    vpnInstanceId: number,
    data: { new_ca_csr_pem: string; old_ca_passphrase: string; expire_days?: number },
  ): Promise<{ message: string; cross_cert_pem: string }> {
    const response = await apiClient.post(`/easyrsa/${vpnInstanceId}/cross-sign`, data)
    return response.data
  },

  // ── Server-level endpoints (no VPN instance required) ─────────────────
  async serverPkiStatus(serverId: number, params: ServerLevelParams): Promise<EasyRsaSettings & { use_sudo: boolean }> {
    const response = await apiClient.post(`/easyrsa/server/${serverId}/pki-status`, params)
    return response.data
  },

  async serverInitPki(serverId: number, params: ServerLevelParams & { force?: boolean }): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/server/${serverId}/init-pki`, params)
    return response.data
  },

  async serverBuildCa(
    serverId: number,
    params: ServerLevelParams & { common_name: string; passphrase: string; expire_days?: number },
  ): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/server/${serverId}/build-ca`, params)
    return response.data
  },

  async serverBuildServer(
    serverId: number,
    params: ServerLevelParams & { common_name: string; passphrase?: string; expire_days?: number },
  ): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/server/${serverId}/build-server`, params)
    return response.data
  },

  async serverGenDh(serverId: number, params: ServerLevelParams): Promise<{ message: string; output: string }> {
    const response = await apiClient.post(`/easyrsa/server/${serverId}/gen-dh`, params)
    return response.data
  },

  async serverRenewCa(
    serverId: number,
    params: ServerLevelParams & { ca_passphrase: string; expire_days?: number },
  ): Promise<{ message: string }> {
    const response = await apiClient.post(`/easyrsa/server/${serverId}/renew-ca`, params)
    return response.data
  },

  async serverCrossSign(
    serverId: number,
    params: ServerLevelParams & { new_ca_csr_pem: string; old_ca_passphrase: string; expire_days?: number },
  ): Promise<{ message: string; cross_cert_pem: string }> {
    const response = await apiClient.post(`/easyrsa/server/${serverId}/cross-sign`, params)
    return response.data
  },
}
