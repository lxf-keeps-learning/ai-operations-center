import { request } from '@/utils/request'

export interface PlatformOverviewMetrics {
  today_requests: number
  running_tasks: number
  pending_messages: number
  failed_tasks: number
  total_tokens: number
  agent_success_rate: number
  average_response_ms: number
}

export interface PlatformOverviewSession {
  id: string
  conversation_id: string
  title: string
  agent: string
  channel: string
  runs: number
  total_tokens: number
  status: string
  updated_at: string
}

export interface PlatformOverview {
  metrics: PlatformOverviewMetrics
  recent_sessions: PlatformOverviewSession[]
}

export function getPlatformOverview(): Promise<PlatformOverview> {
  return request<PlatformOverview>('/platform/overview')
}
