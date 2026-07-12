import apiClient from './client'
import type { SystemInfo } from '@/types'

export const systemApi = {
  async getInfo(): Promise<SystemInfo> {
    const response = await apiClient.get<SystemInfo>('/system/info')
    return response.data
  },
}
