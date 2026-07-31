import { request } from '@/utils/request'
import type {
  EvaluateRequest,
  EvaluationResult,
  EvaluationMetrics,
  TrendItem,
  FailureItem,
  EvaluatorInfo,
  PaginatedResult,
} from '@/types/evaluation-center'

const BASE = '/evaluation'

export function evaluate(data: EvaluateRequest): Promise<EvaluationResult[]> {
  return request<EvaluationResult[]>(`${BASE}/evaluate`, { method: 'POST', body: JSON.stringify(data) })
}

export function getPromptMetrics(promptKey: string): Promise<EvaluationMetrics> {
  return request<EvaluationMetrics>(`${BASE}/prompts/${promptKey}/metrics`)
}

export function getPromptTrends(promptKey: string, days = 7): Promise<TrendItem[]> {
  return request<TrendItem[]>(`${BASE}/prompts/${promptKey}/trends?days=${days}`)
}

export function getPromptFailures(promptKey: string, days = 7): Promise<FailureItem[]> {
  return request<FailureItem[]>(`${BASE}/prompts/${promptKey}/failures?days=${days}`)
}

export function listResults(
  promptKey: string,
  params?: { evaluator_key?: string; passed?: boolean; page?: number; page_size?: number },
): Promise<PaginatedResult<EvaluationResult>> {
  const search = new URLSearchParams()
  if (params?.evaluator_key) search.set('evaluator_key', params.evaluator_key)
  if (params?.passed !== undefined) search.set('passed', String(params.passed))
  if (params?.page) search.set('page', String(params.page))
  if (params?.page_size) search.set('page_size', String(params.page_size))
  const qs = search.toString()
  return request<PaginatedResult<EvaluationResult>>(`${BASE}/prompts/${promptKey}/results${qs ? '?' + qs : ''}`)
}

export function getResult(resultId: number): Promise<EvaluationResult> {
  return request<EvaluationResult>(`${BASE}/results/${resultId}`)
}

export function getResultsByTrace(traceId: string): Promise<EvaluationResult[]> {
  return request<EvaluationResult[]>(`${BASE}/results/by-trace/${traceId}`)
}

export function listEvaluators(): Promise<EvaluatorInfo[]> {
  return request<EvaluatorInfo[]>(`${BASE}/evaluators`)
}

export function calculateMetrics(promptKey: string): Promise<EvaluationMetrics> {
  return request<EvaluationMetrics>(`${BASE}/prompts/${promptKey}/calculate-metrics`, { method: 'POST' })
}
