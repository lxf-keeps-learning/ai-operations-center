import { request } from '@/utils/request'
import type { CollectRequest, FailureSummary, FailureDetail, FailureStats, PaginatedResult } from '@/types/failure-center'

const BASE = '/failures'

export function collectFailures(data: CollectRequest): Promise<FailureDetail[]> {
  return request<FailureDetail[]>(`${BASE}/collect`, { method: 'POST', body: JSON.stringify(data) })
}

export function autoCollect(promptKey: string): Promise<FailureDetail[]> {
  return request<FailureDetail[]>(`${BASE}/auto-collect/${encodeURIComponent(promptKey)}`, { method: 'POST' })
}

export function listFailures(params?: Record<string, string | number | boolean | undefined>): Promise<PaginatedResult<FailureSummary>> {
  const search = new URLSearchParams()
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== '') search.set(k, String(v))
    }
  }
  const qs = search.toString()
  return request<PaginatedResult<FailureSummary>>(`${BASE}${qs ? '?' + qs : ''}`)
}

export function getFailure(failureId: number): Promise<FailureDetail> {
  return request<FailureDetail>(`${BASE}/${failureId}`)
}

export function convertFailure(failureId: number): Promise<FailureDetail> {
  return request<FailureDetail>(`${BASE}/${failureId}/convert`, { method: 'POST' })
}

export function analyzeFailure(failureId: number, analysis: string): Promise<FailureDetail> {
  return request<FailureDetail>(`${BASE}/${failureId}/analyze`, { method: 'POST', body: JSON.stringify({ analysis }) })
}

export function updateFailureStatus(failureId: number, status: string): Promise<FailureDetail> {
  return request<FailureDetail>(`${BASE}/${failureId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
}

export function getFailureStats(promptKey: string): Promise<FailureStats> {
  return request<FailureStats>(`${BASE}/stats/${encodeURIComponent(promptKey)}`)
}
