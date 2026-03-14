import apiClient from './client'
import type { DeployPrerequisites, DeployTaskStatus } from '@/types'

export const deployApi = {
  async checkPrerequisites(serverId: number): Promise<DeployPrerequisites> {
    const response = await apiClient.get<DeployPrerequisites>(
      `/deploy/prerequisites/${serverId}`,
    )
    return response.data
  },

  async startDeployment(
    serverId: number,
    data: {
      install_openvpn?: boolean
      install_easyrsa?: boolean
      openvpn_config_dir?: string
      easyrsa_install_dir?: string
    },
  ): Promise<{ task_id: string; status: string }> {
    const response = await apiClient.post(`/deploy/${serverId}`, data)
    return response.data
  },

  async getStatus(taskId: string): Promise<DeployTaskStatus> {
    const response = await apiClient.get<DeployTaskStatus>(`/deploy/status/${taskId}`)
    return response.data
  },
}
