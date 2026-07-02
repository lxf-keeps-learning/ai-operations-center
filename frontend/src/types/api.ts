export interface ApiEnvelope<T> {
  code: number
  message: string
  traceId?: string
  data: T
}

export interface HealthStatus {
  status: 'UP' | 'DOWN' | string
  database?: 'UP' | 'DOWN' | string
  redis?: 'UP' | 'DOWN' | string
  llm?: 'UP' | 'DOWN' | string
}

export type AgentCode = 'operation' | 'hidden_risk' | string

export interface PageContext {
  page: string
  filters?: Record<string, unknown>
  selected?: Record<string, unknown>
}

export interface BusinessContext {
  object_type: string
  object_id?: string
  refs?: Record<string, unknown>
}

export interface AgentAnalyzeRequest {
  agent_code: AgentCode
  scene_code: string
  message: string
  conversation_id: string | null
  page_context: PageContext
  business_context: BusinessContext
  stream: boolean
}

export interface AgentChatRequest {
  message: string
  conversation_id?: string | null
  agent_code: AgentCode
  page_context: PageContext
  stream: boolean
}

export interface AgentTaskResponse {
  conversation_id: string
  session_id: string
  status?: 'running' | 'success' | 'failed' | 'stopped' | string
  stream_url: string
}

export interface ConversationSummary {
  conversation_id: string
  title: string
  agent_code: AgentCode
  update_time?: string
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface FeedbackRequest {
  conversation_id: string
  session_id: string
  trace_id: string
  score?: number
  attitude?: 'like' | 'dislike'
  comment?: string
}

export interface FeedbackResponse {
  feedback_id: string
}

export type StreamStatus = 'idle' | 'running' | 'streaming' | 'success' | 'failed' | 'stopped'

export type StreamEventName = 'start' | 'progress' | 'token' | 'data' | 'error' | 'done' | 'stop'

export interface StreamEventPayload {
  event: StreamEventName
  traceId?: string
  message?: string
  content?: string
  status?: string
  code?: number
  [key: string]: unknown
}
