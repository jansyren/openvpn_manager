/**
 * Axios instance with:
 * - JWT bearer token injection from auth store
 * - 401 auto-refresh via refresh cookie
 * - Request-ID header
 * - Error normalisation
 */
import axios, { type AxiosInstance, type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'

let _accessToken: string | null = null
let _refreshPromise: Promise<string> | null = null

export function setAccessToken(token: string | null): void {
  _accessToken = token
}

export function getAccessToken(): string | null {
  return _accessToken
}

const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // send refresh cookie
})

function generateRequestId(): string {
  const arr = new Uint8Array(16)
  crypto.getRandomValues(arr) // available in all contexts, unlike randomUUID()
  arr[6] = (arr[6] & 0x0f) | 0x40
  arr[8] = (arr[8] & 0x3f) | 0x80
  return [...arr]
    .map((b, i) => ([4, 6, 8, 10].includes(i) ? '-' : '') + b.toString(16).padStart(2, '0'))
    .join('')
}

// ── Request interceptor: inject Bearer token ──────────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`
  }
  config.headers['X-Request-ID'] = generateRequestId()
  return config
})

// ── Response interceptor: auto-refresh on 401 ─────────────────────────────
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error) => {
    const originalRequest = error.config
    const isAuthEndpoint =
      originalRequest.url?.includes('/auth/refresh') ||
      originalRequest.url?.includes('/auth/logout')

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true

      if (!_refreshPromise) {
        _refreshPromise = refreshAccessToken().finally(() => {
          _refreshPromise = null
        })
      }

      try {
        const newToken = await _refreshPromise
        setAccessToken(newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return apiClient(originalRequest)
      } catch {
        setAccessToken(null)
        window.dispatchEvent(new CustomEvent('auth:logout'))
        return Promise.reject(error)
      }
    }
    return Promise.reject(normalizeError(error))
  }
)

async function refreshAccessToken(): Promise<string> {
  const response = await axios.post(
    '/api/v1/auth/refresh',
    {},
    { withCredentials: true }
  )
  return response.data.access_token
}

export interface ApiError {
  status: number
  detail: string
}

function normalizeError(error: unknown): ApiError {
  if (axios.isAxiosError(error) && error.response) {
    return {
      status: error.response.status,
      detail: error.response.data?.detail ?? 'An error occurred',
    }
  }
  return { status: 0, detail: 'Network error' }
}

export default apiClient
