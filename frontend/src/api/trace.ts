import { request } from '@/utils/request'

export interface Span {
  spanId: string
  parentSpanId: string
  operation: string
  startTime: string
  endTime: string
  status: string
  service: string
  metadata?: Record<string, unknown>
}

export interface TraceData {
  traceId: string
  spans: Span[]
}

export async function getTrace(traceId: string) {
  return request<TraceData>(`/traces/${traceId}`)
}
