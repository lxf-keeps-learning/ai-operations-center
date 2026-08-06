import { request } from '@/utils/request'

export type OperationMessageStatus = 'awaiting_review' | 'claimed' | 'reopened' | 'resolved' | 'failed' | 'processing'
export type OperationMessageTab = 'pending' | 'mine' | 'claimed' | 'resolved' | 'failed'

export interface OperationMessageListParams {
  status?: OperationMessageStatus | 'mine'
  assignee_id?: string
  priority?: number
  report_id?: number
  page?: number
  page_size?: number
}

export interface OperationMessageActionRequest {
  operator_id: string
}

export interface ResolveOperationMessageRequest extends OperationMessageActionRequest {
  note: string
}

export interface OperationMessage {
  id: string
  runtime_session_id: string
  report_chat_message_id: string | null
  report_id: number | null
  priority: number
  status: Exclude<OperationMessageStatus, 'mine'>
  assignee_id: string | null
  claimed_at: string | null
  lease_expires_at: string | null
  resolved_at: string | null
  resolution_note: string | null
  retry_count: number
  error_message: string | null
  created_at: string | null
  updated_at: string | null
  ai_status: string | null
  task_type: string | null
  user_id: string | null
  conversation_id: string | null
  input_text: string | null
  output_text: string | null
  trace_id: string | null
}

export interface OperationMessageSummary {
  awaiting_review: number
  claimed: number
  reopened: number
  resolved: number
  failed: number
  processing: number
  mine: number
}

export async function listOperationMessages(params: OperationMessageListParams = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  return request<OperationMessage[]>(`/operation/messages${query.toString() ? `?${query}` : ''}`)
}

export function getOperationMessageSummary(params: { assignee_id?: string } = {}) {
  const query = new URLSearchParams()
  if (params.assignee_id) query.set('assignee_id', params.assignee_id)
  return request<OperationMessageSummary>(`/operation/messages/summary${query.toString() ? `?${query}` : ''}`)
}

function operatorActionPayload(payload: OperationMessageActionRequest | string): OperationMessageActionRequest {
  return typeof payload === 'string' ? { operator_id: payload } : payload
}

export function claimOperationMessage(id: string, payload: OperationMessageActionRequest | string) {
  return request<OperationMessage>(`/operation/messages/${encodeURIComponent(id)}/claim`, { method: 'POST', body: JSON.stringify(operatorActionPayload(payload)) })
}

export function releaseOperationMessage(id: string, payload: OperationMessageActionRequest | string) {
  return request<OperationMessage>(`/operation/messages/${encodeURIComponent(id)}/release`, { method: 'POST', body: JSON.stringify(operatorActionPayload(payload)) })
}

export function resolveOperationMessage(id: string, payload: ResolveOperationMessageRequest | string, note?: string) {
  const requestPayload = typeof payload === 'string' ? { operator_id: payload, note: note || '' } : payload
  return request<OperationMessage>(`/operation/messages/${encodeURIComponent(id)}/resolve`, { method: 'POST', body: JSON.stringify(requestPayload) })
}

export function reopenOperationMessage(id: string, payload: OperationMessageActionRequest | string) {
  return request<OperationMessage>(`/operation/messages/${encodeURIComponent(id)}/reopen`, { method: 'POST', body: JSON.stringify(operatorActionPayload(payload)) })
}

export function retryOperationMessage(id: string, payload: OperationMessageActionRequest | string) {
  return request<OperationMessage>(`/operation/messages/${encodeURIComponent(id)}/retry`, { method: 'POST', body: JSON.stringify(operatorActionPayload(payload)) })
}
