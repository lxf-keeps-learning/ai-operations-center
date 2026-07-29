export interface EvaluateRequest {
  trace_id?: string
  prompt_key: string
  prompt_version?: string
  graph_name?: string
  node_name?: string
  input: string
  output: string
  schema?: Record<string, unknown>
  required_fields?: string[]
  field_enum_map?: Record<string, string[]>
}

export interface EvaluationResult {
  id: number
  trace_id: string
  prompt_key: string | null
  prompt_version: string | null
  graph_name: string | null
  node_name: string | null
  evaluator_key: string
  evaluator_type: string
  score: number | null
  passed: boolean
  reason: string | null
  violations: string[] | null
  created_at: string
}

export interface EvaluationMetrics {
  prompt_key: string
  total_evaluations: number
  compliance_rate: number
  format_compliance: number
  hallucination_rate: number
  evidence_complete_rate: number
  avg_score: number
  pass_rate: number
}

export interface TrendItem {
  date: string
  evaluator_key: string
  avg_score: number
  count: number
}

export interface FailureItem {
  evaluator_key: string
  failure_count: number
}

export interface EvaluatorInfo {
  key: string
  name: string
  type: string
  description: string
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export const EVALUATOR_KEY_MAP: Record<string, string> = {
  json_format: 'JSON 格式',
  schema_compliance: 'Schema 合规',
  field_completeness: '字段完整性',
  type_check: '类型检查',
  enum_check: '枚举值检查',
  no_empty_array: '数组非空',
  response_length: '响应长度',
  question_answered: '回答问题',
  data_grounded: '基于数据',
  no_hallucination: '无虚构',
  evidence_provided: '提供依据',
  actionable_advice: '可执行建议',
  rule_compliance: '规则遵守',
}

export const EVALUATOR_TYPE_MAP: Record<string, string> = {
  deterministic: '代码检查',
  llm_judge: 'LLM 评估',
}
