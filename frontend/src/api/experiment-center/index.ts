import { request } from '@/utils/request'
import type {
  ExperimentCreate,
  ExperimentSummary,
  ExperimentDetail,
  CompareResult,
  ExperimentResultRow,
  PaginatedResult,
} from '@/types/experiment-center'

const BASE = '/experiments'

export function listExperiments(page = 1, pageSize = 20): Promise<PaginatedResult<ExperimentSummary>> {
  return request<PaginatedResult<ExperimentSummary>>(`${BASE}?page=${page}&page_size=${pageSize}`)
}

export function createExperiment(data: ExperimentCreate): Promise<ExperimentDetail> {
  return request<ExperimentDetail>(`${BASE}`, { method: 'POST', body: JSON.stringify(data) })
}

export function getExperiment(experimentId: number): Promise<ExperimentDetail> {
  return request<ExperimentDetail>(`${BASE}/${experimentId}`)
}

export function runExperiment(experimentId: number): Promise<ExperimentDetail> {
  return request<ExperimentDetail>(`${BASE}/${experimentId}/run`, { method: 'POST' })
}

export function compareExperiment(experimentId: number): Promise<CompareResult> {
  return request<CompareResult>(`${BASE}/${experimentId}/compare`)
}

export function getExperimentResults(experimentId: number, version?: string): Promise<ExperimentResultRow[]> {
  const qs = version ? `?version=${version}` : ''
  return request<ExperimentResultRow[]>(`${BASE}/${experimentId}/results${qs}`)
}
