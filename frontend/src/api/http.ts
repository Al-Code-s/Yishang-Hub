import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'

/**
 * 统一 HTTP 客户端。
 *
 * 约定（与后端 docs/api-conventions.md 一致）：
 * - 同源部署，会话 Cookie 随请求发送（withCredentials）；
 * - 所有写操作携带 X-CSRFToken，令牌取自 yishang_csrftoken Cookie；
 * - 错误统一转换为 ApiError，保留后端返回的 code / message / details / request_id；
 * - 不做「失败也当成功」的兜底，异常必须暴露给调用方。
 */

export interface ApiErrorPayload {
  code: string
  message: string
  details: Record<string, unknown>
  request_id: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly requestId: string

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message || '请求失败')
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code || 'ERROR'
    this.details = payload.details ?? {}
    this.requestId = payload.request_id ?? ''
  }

  /** 字段级错误：{ 字段名: [提示...] } */
  get fieldErrors(): Record<string, string[]> {
    const result: Record<string, string[]> = {}
    for (const [key, value] of Object.entries(this.details)) {
      if (Array.isArray(value)) {
        result[key] = value.map((item) => String(item))
      } else if (typeof value === 'string') {
        result[key] = [value]
      }
    }
    return result
  }

  /** 字段级错误拍平成一句话，用于表单顶部提示。 */
  get fieldErrorMessage(): string {
    const parts: string[] = []
    for (const [field, messages] of Object.entries(this.fieldErrors)) {
      parts.push(`${field}：${messages.join('；')}`)
    }
    return parts.join('  ')
  }
}

const CSRF_COOKIE_NAME = 'yishang_csrftoken'
const SAFE_METHODS = new Set(['get', 'head', 'options'])

export function readCookie(name: string): string {
  const target = `${name}=`
  for (const item of document.cookie.split(';')) {
    const trimmed = item.trim()
    if (trimmed.startsWith(target)) {
      return decodeURIComponent(trimmed.slice(target.length))
    }
  }
  return ''
}

const baseURL = import.meta.env.VITE_API_BASE ?? '/api/v1'

export const http: AxiosInstance = axios.create({
  baseURL,
  withCredentials: true,
  timeout: 30000,
  headers: { Accept: 'application/json' },
})

http.interceptors.request.use((config) => {
  const method = (config.method ?? 'get').toLowerCase()
  if (!SAFE_METHODS.has(method)) {
    const token = readCookie(CSRF_COOKIE_NAME)
    if (token) {
      config.headers.set('X-CSRFToken', token)
    }
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const data = error.response.data as Partial<ApiErrorPayload> & Record<string, unknown>
      if (data && typeof data === 'object' && typeof data.code === 'string') {
        return Promise.reject(
          new ApiError(error.response.status, {
            code: data.code,
            message: String(data.message ?? '请求失败'),
            details: (data.details as Record<string, unknown>) ?? {},
            request_id: String(data.request_id ?? ''),
          }),
        )
      }
      return Promise.reject(
        new ApiError(error.response.status, {
          code: 'HTTP_ERROR',
          message: `请求失败（HTTP ${error.response.status}）`,
          details: {},
          request_id: '',
        }),
      )
    }
    return Promise.reject(
      new ApiError(0, {
        code: 'NETWORK_ERROR',
        message: '无法连接服务器，请检查网络后重试。',
        details: {},
        request_id: '',
      }),
    )
  },
)

export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return (await http.get<T>(url, config)).data
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await http.post<T>(url, data, config)).data
}

export async function patch<T>(url: string, data?: unknown): Promise<T> {
  return (await http.patch<T>(url, data)).data
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  return (await http.put<T>(url, data)).data
}

export async function del(url: string): Promise<void> {
  await http.delete(url)
}