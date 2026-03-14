import apiClient from './client'
import type { CertificateRead } from '@/types'

export const certificatesApi = {
  async list(vpnInstanceId?: number): Promise<CertificateRead[]> {
    const params = vpnInstanceId ? { vpn_instance_id: vpnInstanceId } : {}
    const response = await apiClient.get<CertificateRead[]>('/certificates', { params })
    return response.data
  },

  async revoke(id: number, reason: string, caPassphrase?: string): Promise<void> {
    await apiClient.post(`/certificates/${id}/revoke`, {
      reason: reason || 'unspecified',
      ca_passphrase: caPassphrase ?? null,
    })
  },

  async renew(
    id: number,
    caPassphrase: string,
    expireDays = 825,
  ): Promise<{ message: string; serial: string }> {
    const response = await apiClient.post(`/certificates/${id}/renew`, {
      ca_passphrase: caPassphrase,
      expire_days: expireDays,
    })
    return response.data
  },
}
