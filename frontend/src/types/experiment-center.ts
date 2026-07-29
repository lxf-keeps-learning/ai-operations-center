export interface ExperimentCreate {
  name: string
  description?: string
  prompt_id: number
  source_version_id: number
  target_version_id: number
  test_case_ids: number[]
}

export interface ExperimentSummary {
  id: number
  name: string
  status: ExperimentStatus
  winner_version: string | null
  source_version: string
  target_version: string
  total_samples: number
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface ExperimentDetail extends ExperimentSummary {
  description: string | null
  prompt_id: number
  source_version_id: number
  target_version_id: number
  completed_samples: number
  summary: Record<string, unknown> | null
}

export type ExperimentStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface VersionMetricSummary {
  version: string
  metrics: Record<string, number>
  avg_tokens: number
  avg_latency_ms: number
  sample_count: number
}

export interface MetricComparison {
  metric_key: string
  source_score: number
  target_score: number
  diff: number
  better: 'source' | 'target' | 'draw'
}

export interface CompareResult {
  experiment_id: number
  experiment_name: string
  status: string
  winner: string
  source_version: VersionMetricSummary
  target_version: VersionMetricSummary
  metric_comparisons: MetricComparison[]
}

export interface ExperimentResultRow {
  id: number
  version: string
  test_case_id: number | null
  raw_output: string | null
  token_usage: Record<string, number> | null
  latency_ms: number | null
  metrics: EvaluationMetric[] | null
  status: string
  created_at: string
}

export interface EvaluationMetric {
  evaluator_key: string
  score: number
  passed: boolean
  reason?: string
}

export const EXPERIMENT_STATUS_MAP: Record<ExperimentStatus, string> = {
  pending: '待运行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

export const WINNER_MAP: Record<string, string> = {
  source: '源版本胜出',
  target: '目标版本胜出',
  draw: '平局',
  pending: '待定',
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
