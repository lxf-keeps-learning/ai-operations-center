import { request } from '@/utils/request'

export interface AnalysisRecord {
  id: number
  trace_id: string
  report_name: string | null
  domain: string
  time_dimension: string | null
  analysis_date: string | null
  status: string
  summary_text: string | null
  final_answer_markdown: string | null
  page_context: Record<string, unknown> | null
  advice_items: Record<string, unknown> | null
  evidence: Record<string, unknown> | null
  created_at: string | null
}

export interface AnalysisRecordDetail extends AnalysisRecord {
  error_message: string | null
  abnormal_items: Record<string, unknown> | null
  risk_items: Record<string, unknown> | null
  model_name: string | null
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

export async function listRecords(params: {
  domain?: string
  page?: number
  page_size?: number
}) {
  const query = new URLSearchParams()
  if (params.domain) query.set('domain', params.domain)
  if (params.page) query.set('page', String(params.page))
  if (params.page_size) query.set('page_size', String(params.page_size))
  const path = query.toString() ? `/operation/records?${query}` : '/operation/records'
  return request<AnalysisRecord[]>(path)
}

export async function getRecordDetail(id: number) {
  return request<AnalysisRecordDetail>(`/operation/records/${id}`)
}

export function getDownloadUrl(id: number): string {
  const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  return `${base}/operation/records/${id}/download`
}
