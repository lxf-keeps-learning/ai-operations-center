import { request } from '@/utils/request'

export type GraphType = 'report_generation' | 'report_chat'

export interface GraphRunSummary {
  run_id: string
  graph_type: GraphType
  graph_name: string
  title: string
  status: string
  trace_id: string | null
  session_id: string | null
  summary: string | null
  created_at: string | null
}

export interface GraphRunEvent {
  id: string
  sequence: number
  event_type: string
  node_key?: string | null
  node_name?: string | null
  status?: string | null
  message?: string | null
  duration_ms?: number | null
  source_label?: string | null
  payload?: Record<string, unknown> | null
  error_message?: string | null
  timestamp?: string | null
}

export interface GraphRunDetail extends GraphRunSummary {
  input: Record<string, unknown> | null
  output: Record<string, unknown> | null
  events: GraphRunEvent[]
  traces: Array<Record<string, unknown>>
}

export function listGraphRuns(graphType?: GraphType): Promise<GraphRunSummary[]> {
  const query = graphType ? `?graph_type=${graphType}` : ''
  return request<GraphRunSummary[]>(`/operation/graph-runs${query}`)
}

export function getGraphRunDetail(type: GraphType, runId: string): Promise<GraphRunDetail> {
  return request<GraphRunDetail>(`/operation/graph-runs/${type}/${encodeURIComponent(runId)}`)
}
