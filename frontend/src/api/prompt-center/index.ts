import { request } from '@/utils/request'
import type {
  PromptDefinition,
  PromptDetail,
  PromptVersion,
  PromptVersionSummary,
  VersionCreate,
  VersionCompare,
  RenderResult,
  TestCase,
  TestCaseCreate,
  TestRun,
  EvaluationSummary,
  Release,
  ReleaseRequest,
  PromptMetrics,
  PaginatedResult,
} from '@/types/prompt-center'

const BASE = '/prompt-center/prompts'

export function listPrompts(params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResult<PromptDefinition>> {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const query = search.toString()
  return request<PaginatedResult<PromptDefinition>>(`${BASE}${query ? `?${query}` : ''}`)
}

export function getPrompt(promptId: number): Promise<PromptDetail> {
  return request<PromptDetail>(`${BASE}/${promptId}`)
}

export function createPrompt(data: Partial<PromptDefinition> & { prompt_key: string; prompt_name: string }): Promise<PromptDefinition> {
  return request<PromptDefinition>(`${BASE}`, { method: 'POST', body: JSON.stringify(data) })
}

export function updatePrompt(promptId: number, data: Partial<PromptDefinition>): Promise<PromptDefinition> {
  return request<PromptDefinition>(`${BASE}/${promptId}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deletePrompt(promptId: number): Promise<null> {
  return request<null>(`${BASE}/${promptId}`, { method: 'DELETE' })
}

export function getPromptMetrics(promptId: number): Promise<PromptMetrics> {
  return request<PromptMetrics>(`${BASE}/${promptId}/metrics`)
}

export function listVersions(promptId: number): Promise<PromptVersionSummary[]> {
  return request<PromptVersionSummary[]>(`${BASE}/${promptId}/versions`)
}

export function getVersion(promptId: number, versionId: number): Promise<PromptVersion> {
  return request<PromptVersion>(`${BASE}/${promptId}/versions/${versionId}`)
}

export function createVersion(promptId: number, data: VersionCreate): Promise<PromptVersion> {
  return request<PromptVersion>(`${BASE}/${promptId}/versions`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateVersion(promptId: number, versionId: number, data: Partial<VersionCreate>): Promise<PromptVersion> {
  return request<PromptVersion>(`${BASE}/${promptId}/versions/${versionId}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function submitVersion(promptId: number, versionId: number): Promise<PromptVersion> {
  return request<PromptVersion>(`${BASE}/${promptId}/versions/${versionId}/submit`, { method: 'POST' })
}

export function approveVersion(promptId: number, versionId: number, comment?: string): Promise<PromptVersion> {
  return request<PromptVersion>(`${BASE}/${promptId}/versions/${versionId}/approve`, { method: 'POST', body: JSON.stringify({ comment }) })
}

export function rejectVersion(promptId: number, versionId: number, comment?: string): Promise<PromptVersion> {
  return request<PromptVersion>(`${BASE}/${promptId}/versions/${versionId}/reject`, { method: 'POST', body: JSON.stringify({ comment }) })
}

export function compareVersions(promptId: number, sourceVersionId: number, targetVersionId: number): Promise<VersionCompare> {
  return request<VersionCompare>(
    `${BASE}/${promptId}/compare?source_version_id=${sourceVersionId}&target_version_id=${targetVersionId}`,
  )
}

export function renderPrompt(promptKey: string, variables?: Record<string, unknown>, environment?: string): Promise<RenderResult> {
  return request<RenderResult>(`${BASE}/render`, { method: 'POST', body: JSON.stringify({ prompt_key: promptKey, variables: variables || {}, environment: environment || 'development' }) })
}

export function previewPrompt(promptId: number, versionId: number, variables?: Record<string, unknown>): Promise<RenderResult> {
  return request<RenderResult>(`${BASE}/${promptId}/preview`, {
    method: 'POST',
    body: JSON.stringify({
      prompt_id: promptId,
      version_id: versionId,
      variables: variables || {},
    }),
  })
}

export function listTestCases(promptId: number): Promise<TestCase[]> {
  return request<TestCase[]>(`${BASE}/${promptId}/test-cases`)
}

export function createTestCase(promptId: number, data: TestCaseCreate): Promise<TestCase> {
  return request<TestCase>(`${BASE}/${promptId}/test-cases`, { method: 'POST', body: JSON.stringify(data) })
}

export function runTest(promptId: number, versionId: number, inputData: Record<string, unknown>, testCaseId?: number): Promise<TestRun> {
  return request<TestRun>(`${BASE}/${promptId}/versions/${versionId}/test`, { method: 'POST', body: JSON.stringify({ input_data: inputData, test_case_id: testCaseId }) })
}

export function runDatasetTest(promptId: number, versionId: number, testCaseIds: number[]): Promise<TestRun[]> {
  return request<TestRun[]>(`${BASE}/${promptId}/versions/${versionId}/dataset-test`, { method: 'POST', body: JSON.stringify({ test_case_ids: testCaseIds }) })
}

export function listTestRuns(promptId: number, page?: number, pageSize?: number): Promise<TestRun[]> {
  const params = new URLSearchParams()
  if (page) params.set('page', String(page))
  if (pageSize) params.set('page_size', String(pageSize))
  const qs = params.toString()
  return request<TestRun[]>(`${BASE}/${promptId}/test-runs${qs ? '?' + qs : ''}`)
}

export function getTestRun(runId: number): Promise<TestRun> {
  return request<TestRun>(`${BASE.replace('/prompts', '/prompt-test-runs')}/${runId}`)
}

export function getTestRunEvaluation(runId: number): Promise<EvaluationSummary> {
  const path = `${BASE.replace('/prompts', '/prompt-test-runs')}/${runId}/evaluation`
  return request<EvaluationSummary>(path)
}

export function grayRelease(promptId: number, versionId: number, data: ReleaseRequest): Promise<Release> {
  return request<Release>(`${BASE}/${promptId}/versions/${versionId}/gray-release`, { method: 'POST', body: JSON.stringify(data) })
}

export function publishVersion(promptId: number, versionId: number, data: ReleaseRequest): Promise<Release> {
  return request<Release>(`${BASE}/${promptId}/versions/${versionId}/publish`, { method: 'POST', body: JSON.stringify(data) })
}

export function rollbackVersion(promptId: number, environment: string, releaseNote?: string): Promise<Release> {
  return request<Release>(`${BASE}/${promptId}/rollback`, { method: 'POST', body: JSON.stringify({ environment, release_note: releaseNote }) })
}

export function listReleases(promptId: number): Promise<Release[]> {
  return request<Release[]>(`${BASE}/${promptId}/releases`)
}
