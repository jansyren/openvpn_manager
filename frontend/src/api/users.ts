import apiClient from './client'
import type { UserManagementRead, UserCreate, UserUpdate } from '@/types'

export const usersApi = {
  async list(): Promise<UserManagementRead[]> {
    const response = await apiClient.get<UserManagementRead[]>('/users')
    return response.data
  },

  async create(data: UserCreate): Promise<UserManagementRead> {
    const response = await apiClient.post<UserManagementRead>('/users', data)
    return response.data
  },

  async update(id: number, data: UserUpdate): Promise<UserManagementRead> {
    const response = await apiClient.put<UserManagementRead>(`/users/${id}`, data)
    return response.data
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/users/${id}`)
  },
}
