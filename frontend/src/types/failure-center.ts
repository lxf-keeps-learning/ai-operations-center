export interface CollectRequest {
  prompt_key?: string
  eval_result_ids?: number[]
  auto_convert?: boolean
}

export interface FailureSummary {
  id: number
  trace_id: string | null
  prompt_key: string | null
  prompt_version: string | null
  failure_type: string
  severity: string
  reason: string | null
  status: string
  eval_score: number | null
  created_at: string
  updated_at: string
}

export interface EvalResultRef {
  id: number
  evaluator_key: string
  evaluator_type: string
  score: number | null
  passed: boolean
  reason: string | null
  violations: string[] | null
  created_at: string
}

export interface FailureDetail extends FailureSummary {
  graph_name: string | null
  node_name: string | null
  input: string | null
  output: string | null
  analysis: string | null
  eval_result_ids: number[] | null
  generated_case_id: number | null
  eval_results: EvalResultRef[]
  created_by: string | null
}

export interface FailureStats {
  total: number
  by_type: Record<string, number>
  by_severity: Record<string, number>
  by_status: Record<string, number>
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export const FAILURE_TYPE_LABELS: Record<string, string> = {
  json_format: 'JSON 格式错误',
  schema_compliance: 'Schema 不合规',
  field_missing: '字段缺失',
  hallucination: '虚构数据',
  not_answered: '未回答问题',
  not_grounded: '未基于数据',
  no_evidence: '缺少依据',
  vague_advice: '建议空泛',
  timeout: '超时',
  llm_error: 'LLM 异常',
  unknown: '未知',
}

export const SEVERITY_MAP: Record<string, { label: string; type: string }> = {
  critical: { label: '严重', type: 'danger' },
  high: { label: '高', type: 'warning' },
  medium: { label: '中', type: 'info' },
  low: { label: '低', type: '' },
}

export const STATUS_MAP: Record<string, { label: string; type: string }> = {
  pending: { label: '待处理', type: 'info' },
  analyzed: { label: '已分析', type: 'warning' },
  converted: { label: '已转化', type: 'success' },
  resolved: { label: '已解决', type: '' },
}
