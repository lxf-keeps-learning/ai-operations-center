/**
 * HTTP 请求工具 — 统一封装 fetch，注入 X-Trace-Id 请求头
 *
 * 所有 API 请求均通过此模块发起，统一处理：
 *   1. 自动注入 traceId（前后端全链路追踪）
 *   2. 统一超时控制（默认 15s）
 *   3. 统一错误处理（ApiRequestError）
 *   4. 业务错误码判断（code !== 0 视为失败）
 *   5. 自动解析后端统一响应格式 { code, message, traceId, data }
 *
 * 使用方法：
 *   import { request } from '@/utils/request'
 *   const data = await request<ResponseType>('/path/to/api', { method: 'POST', body: JSON.stringify(params) })
 */

import { createTraceId, setLastTraceId } from '@/utils/trace'

const DEFAULT_TIMEOUT = 15_000

export const apiBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL || '/api/v1')

interface RequestOptions extends RequestInit {
  timeout?: number
}

export class ApiRequestError extends Error {
  code?: number
  status?: number
  traceId?: string

  constructor(message: string, options: { code?: number; status?: number; traceId?: string } = {}) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = options.code
    this.status = options.status
    this.traceId = options.traceId
  }
}

export function buildApiUrl(
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>,
) {
  const pathname = `${apiBaseUrl}${normalizePath(path)}`

  if (!query) {
    return pathname
  }

  const search = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })

  const queryString = search.toString()
  return queryString ? `${pathname}?${queryString}` : pathname
}

export async function request<T>(path: string, options: RequestOptions = {}) {
  const controller = new AbortController()
  const timeout = options.timeout ?? DEFAULT_TIMEOUT
  const timeoutId = window.setTimeout(() => controller.abort(), timeout)
  const headers = new Headers(options.headers)
  const traceId = createTraceId()

  headers.set('X-Trace-Id', traceId)

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  try {
    const response = await fetch(buildApiUrl(path), {
      ...options,
      headers,
      signal: options.signal ?? controller.signal,
    })
    const text = await response.text()
    const payload: { code: number; message: string; traceId?: string; data: T } | null = text
      ? JSON.parse(text)
      : null
    const responseTraceId = response.headers.get('X-Trace-Id') || payload?.traceId || traceId

    setLastTraceId(responseTraceId)

    if (!response.ok) {
      throw new ApiRequestError(payload?.message || `HTTP ${response.status}`, {
        code: payload?.code,
        status: response.status,
        traceId: responseTraceId,
      })
    }

    if (!payload) {
      throw new ApiRequestError('后端返回为空', {
        status: response.status,
        traceId: responseTraceId,
      })
    }

    if (typeof payload.code === 'number' && payload.code !== 0) {
      throw new ApiRequestError(payload.message || '接口调用失败', {
        code: payload.code,
        status: response.status,
        traceId: responseTraceId,
      })
    }

    return payload.data
  } catch (error) {
    if (error instanceof ApiRequestError) {
      throw error
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiRequestError('请求超时，请检查后端服务状态')
    }

    throw new ApiRequestError(error instanceof Error ? error.message : '接口调用失败')
  } finally {
    window.clearTimeout(timeoutId)
  }
}

function normalizeBaseUrl(url: string) {
  return url.endsWith('/') ? url.slice(0, -1) : url
}

function normalizePath(path: string) {
  return path.startsWith('/') ? path : `/${path}`
}
