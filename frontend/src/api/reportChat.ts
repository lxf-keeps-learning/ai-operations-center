import { request } from '@/utils/request'

export type ReportQuestionScope =
  | 'report_internal'
  | 'report_related'
  | 'ioc_global'
  | 'out_of_scope'

export interface ReportChatSession {
  conversation_id: string
  session_id: string
  report_id: number
  title: string
}

export interface RagSource {
  source_id: string
  document_title: string
  content?: string
  score?: number | null
  metadata?: Record<string, unknown>
}

export interface ReportChatMessage {
  runtime_session_id?: string | null
  role: 'user' | 'assistant'
  content: string
  evidence_refs: string[]
  question_scope: ReportQuestionScope | null
  created_at: string
  used_rag?: boolean
  rag_source_refs?: string[]
  rag_sources?: RagSource[]
}

export interface ReportChatMessagesResponse {
  conversation_id: string
  session_id: string
  messages: ReportChatMessage[]
}

export interface SendReportChatMessageResponse {
  trace_id: string
  conversation_id: string
  session_id: string
  runtime_session_id: string
  message_id: string
  question_scope: ReportQuestionScope
  answer: string
  evidence_refs: string[]
  query_scope?: Record<string, unknown>
  answer_type: 'normal' | 'insufficient_evidence' | 'boundary'
  used_rag: boolean
  rag_source_refs: string[]
  rag_sources: RagSource[]
}

export async function createReportChatSession(reportId: number, userId = 'anonymous') {
  return request<ReportChatSession>(`/reports/${reportId}/chat/sessions`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  })
}

export async function getRecentReportChatSession(reportId: number, userId = 'anonymous') {
  const query = new URLSearchParams({ user_id: userId })
  return request<ReportChatSession | null>(`/reports/${reportId}/chat/session?${query.toString()}`)
}

export async function getReportChatMessages(sessionId: string) {
  return request<ReportChatMessagesResponse>(`/chat/sessions/${sessionId}/messages`)
}

export async function sendReportChatMessage(params: {
  sessionId: string
  reportId: number
  question: string
}) {
  return request<SendReportChatMessageResponse>(`/chat/sessions/${params.sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      report_id: params.reportId,
      question: params.question,
    }),
    timeout: 120_000,
  })
}
