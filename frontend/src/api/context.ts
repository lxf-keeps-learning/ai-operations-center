import { request } from '@/utils/request'

export interface ContextData {
  requestContext: {
    traceId: string
    requestTime: string | null
    clientIp: string
    userAgent: string
    method: string
    path: string
  }
  userContext: {
    userId: string
    username: string
    orgId: string
    roles: string[]
    permissions: string[]
  }
  pageContext: {
    pageCode: string
    filters: Record<string, unknown>
    selectedObjectId: string
  }
}

export async function getCurrentContext() {
  return request<ContextData>('/context/current')
}
