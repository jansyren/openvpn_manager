import apiClient from './client'
import type {
  LdapConfigRead,
  LdapConfigCreate,
  LdapConfigUpdate,
  LdapGroupRoleMappingRead,
  LdapGroupRoleMappingCreate,
  VpnInstanceLdapGroupRead,
  VpnInstanceLdapGroupCreate,
  LdapTestResult,
  LdapSyncResult,
  LdapDeployResult,
} from '@/types'

export const ldapApi = {
  // ── LDAP Configs ──────────────────────────────────────────────────────
  async listConfigs(): Promise<LdapConfigRead[]> {
    const res = await apiClient.get<LdapConfigRead[]>('/ldap/configs')
    return res.data
  },

  async createConfig(data: LdapConfigCreate): Promise<LdapConfigRead> {
    const res = await apiClient.post<LdapConfigRead>('/ldap/configs', data)
    return res.data
  },

  async getConfig(id: number): Promise<LdapConfigRead> {
    const res = await apiClient.get<LdapConfigRead>(`/ldap/configs/${id}`)
    return res.data
  },

  async updateConfig(id: number, data: LdapConfigUpdate): Promise<LdapConfigRead> {
    const res = await apiClient.put<LdapConfigRead>(`/ldap/configs/${id}`, data)
    return res.data
  },

  async deleteConfig(id: number): Promise<void> {
    await apiClient.delete(`/ldap/configs/${id}`)
  },

  async testConfig(id: number): Promise<LdapTestResult> {
    const res = await apiClient.post<LdapTestResult>(`/ldap/configs/${id}/test`)
    return res.data
  },

  // ── Group Role Mappings ───────────────────────────────────────────────
  async listGroupMappings(configId: number): Promise<LdapGroupRoleMappingRead[]> {
    const res = await apiClient.get<LdapGroupRoleMappingRead[]>(`/ldap/configs/${configId}/group-mappings`)
    return res.data
  },

  async createGroupMapping(configId: number, data: LdapGroupRoleMappingCreate): Promise<LdapGroupRoleMappingRead> {
    const res = await apiClient.post<LdapGroupRoleMappingRead>(`/ldap/configs/${configId}/group-mappings`, data)
    return res.data
  },

  async deleteGroupMapping(configId: number, mappingId: number): Promise<void> {
    await apiClient.delete(`/ldap/configs/${configId}/group-mappings/${mappingId}`)
  },

  // ── VPN Instance LDAP Groups ──────────────────────────────────────────
  async listVpnGroups(instanceId: number): Promise<VpnInstanceLdapGroupRead[]> {
    const res = await apiClient.get<VpnInstanceLdapGroupRead[]>(`/ldap/vpn-instances/${instanceId}/groups`)
    return res.data
  },

  async addVpnGroup(instanceId: number, data: VpnInstanceLdapGroupCreate): Promise<VpnInstanceLdapGroupRead> {
    const res = await apiClient.post<VpnInstanceLdapGroupRead>(`/ldap/vpn-instances/${instanceId}/groups`, data)
    return res.data
  },

  async removeVpnGroup(instanceId: number, groupId: number): Promise<void> {
    await apiClient.delete(`/ldap/vpn-instances/${instanceId}/groups/${groupId}`)
  },

  async deployLdapPlugin(instanceId: number): Promise<LdapDeployResult> {
    const res = await apiClient.post<LdapDeployResult>(`/ldap/vpn-instances/${instanceId}/deploy`)
    return res.data
  },

  async syncLdapUsers(instanceId: number): Promise<LdapSyncResult> {
    const res = await apiClient.post<LdapSyncResult>(`/ldap/vpn-instances/${instanceId}/sync`)
    return res.data
  },
}
