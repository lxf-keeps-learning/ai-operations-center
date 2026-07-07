import { request } from '@/utils/request'

export interface OperationResult {
  trace_id: string
  status: string
  summary: string
  abnormal_items: Record<string, unknown>[]
  risk_items: Record<string, unknown>[]
  advice_items: Record<string, unknown>[]
  evidence: Record<string, unknown>[]
  errors: Record<string, unknown>[]
}

export interface OperationAnalyzeParams {
  trigger_type?: string
  domain?: string
  active_tab?: string
  time_dimension?: string
  date?: string
  company_id?: string
  project_id?: string
  user_question?: string
}

export async function analyzeOperation(params: OperationAnalyzeParams) {
  return request<OperationResult>('/operation/analyze', {
    method: 'POST',
    body: JSON.stringify(params),
    timeout: 120_000,
  })
}
