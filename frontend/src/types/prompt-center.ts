export interface PromptDefinition {
  id: number
  prompt_key: string
  prompt_name: string
  business_scene: string | null
  graph_name: string | null
  node_name: string | null
  description: string | null
  owner_id: string | null
  current_version_id: number | null
  status: PromptStatus
  created_by: string | null
  created_at: string
  updated_by: string | null
  updated_at: string
}

export interface PromptDetail extends PromptDefinition {
  variables: PromptVariable[]
  versions: PromptVersionSummary[]
}

export interface PromptVersionSummary {
  id: number
  version: string
  status: PromptStatus
  change_reason: string | null
  created_by: string | null
  created_at: string
}

export interface PromptVariable {
  variable_key: string
  variable_name: string
  description: string | null
  data_type: string
  source_type: string
  source_path: string | null
  required: boolean
  default_value: string | null
  example_value: string | null
  sensitive: boolean
  editable: boolean
  display_order: number
}

export type PromptStatus =
  | 'draft'
  | 'testing'
  | 'reviewing'
  | 'approved'
  | 'rejected'
  | 'gray'
  | 'published'
  | 'offline'
  | 'archived'

export interface PromptVersion {
  id: number
  prompt_id: number
  version: string
  system_content: string | null
  business_role_content: string | null
  business_goal_content: string | null
  business_rules: RuleItem[] | null
  output_requirement: string | null
  positive_examples: ExampleItem[] | null
  negative_examples: ExampleItem[] | null
  llm_config: Record<string, unknown> | null
  output_schema: Record<string, unknown> | null
  langsmith_commit_hash: string | null
  langsmith_tag: string | null
  status: PromptStatus
  change_reason: string | null
  created_by: string | null
  created_at: string
}

export interface RuleItem {
  key: string
  content: string
  enabled: boolean
  required: boolean
  display_order: number
}

export interface ExampleItem {
  title: string
  content: string
  description?: string
}

export interface VersionCreate {
  system_content?: string
  business_role_content?: string
  business_goal_content?: string
  business_rules?: RuleItem[]
  output_requirement?: string
  positive_examples?: ExampleItem[]
  negative_examples?: ExampleItem[]
  llm_config?: Record<string, unknown>
  output_schema?: Record<string, unknown>
  change_reason?: string
}

export interface VersionCompare {
  source_version: PromptVersion
  target_version: PromptVersion
  diffs: DiffItem[]
}

export interface DiffItem {
  field: string
  field_label: string
  source_value: string | null
  target_value: string | null
  change_type: 'modified' | 'added' | 'removed' | 'unchanged'
}

export interface RenderResult {
  prompt_id: number
  prompt_key: string
  prompt_name: string
  version: string
  environment: string
  messages: MessageItem[]
  variables: Record<string, unknown>
  model_config: Record<string, unknown>
  output_schema: Record<string, unknown> | null
  langsmith_commit_hash: string | null
  langsmith_tag: string | null
}

export interface MessageItem {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface TestCase {
  id: number
  prompt_id: number
  case_name: string
  case_type: string
  input_data: Record<string, unknown>
  expected_output: string | null
  source_trace_id: string | null
  enabled: boolean
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface TestCaseCreate {
  case_name: string
  case_type?: string
  input_data: Record<string, unknown>
  expected_output?: string
  source_trace_id?: string
}

export interface TestRun {
  id: number
  prompt_id: number
  version_id: number
  test_case_id: number | null
  model_name: string | null
  input_data: Record<string, unknown>
  rendered_prompt: string | null
  raw_output: string | null
  structured_output: Record<string, unknown> | null
  token_usage: { input_tokens: number; output_tokens: number; total_tokens: number } | null
  latency: number | null
  trace_id: string | null
  status: string
  evaluations: Evaluation[]
  created_by: string | null
  created_at: string
}

export interface Evaluation {
  id: number
  test_run_id: number
  evaluator_key: string
  evaluator_type: string
  score: number | null
  passed: boolean
  reason: string | null
  violations: string[] | null
  created_at: string
}

export interface EvaluationSummary {
  total_checks: number
  passed_checks: number
  compliance_rate: number
  evaluations: Evaluation[]
}

export interface Release {
  id: number
  prompt_id: number
  version_id: number
  environment: string
  release_type: string
  traffic_ratio: number | null
  status: string
  approved_by: string | null
  released_by: string | null
  released_at: string
  rollback_version_id: number | null
  release_note: string | null
}

export interface ReleaseRequest {
  environment: string
  release_type?: string
  traffic_ratio?: number
  release_note?: string
  approved_by?: string
  released_by?: string
}

export interface PromptMetrics {
  prompt_id: number
  prompt_key: string
  compliance_rate: number | null
  format_compliance: number | null
  no_fabrication_rate: number | null
  evidence_complete_rate: number | null
  avg_tokens: number | null
  avg_latency_ms: number | null
  satisfaction_score: number | null
  total_runs: number
  total_failures: number
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export const PROMPT_STATUS_OPTIONS: { label: string; value: PromptStatus }[] = [
  { label: '草稿', value: 'draft' },
  { label: '测试中', value: 'testing' },
  { label: '待审核', value: 'reviewing' },
  { label: '审核通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' },
  { label: '灰度中', value: 'gray' },
  { label: '已发布', value: 'published' },
  { label: '已下线', value: 'offline' },
  { label: '已归档', value: 'archived' },
]

export const PROMPT_STATUS_MAP: Record<PromptStatus, string> = {
  draft: '草稿',
  testing: '测试中',
  reviewing: '待审核',
  approved: '审核通过',
  rejected: '已驳回',
  gray: '灰度中',
  published: '已发布',
  offline: '已下线',
  archived: '已归档',
}

export const ENVIRONMENT_OPTIONS = [
  { label: '开发环境', value: 'development' },
  { label: '测试环境', value: 'testing' },
  { label: '预发环境', value: 'staging' },
  { label: '生产环境', value: 'production' },
]
