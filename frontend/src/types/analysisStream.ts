export type AnalysisEventType =
  | 'analysis_started'
  | 'node_started'
  | 'node_completed'
  | 'node_failed'
  | 'report_completed'
  | 'report_delta'
  | 'analysis_failed'
  | 'cancelled'
  | 'heartbeat'
  | 'stream_closed'

export type AnalysisEventStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface AnalysisStreamEvent {
  run_id: string
  event_id: string
  sequence: number
  event_type: AnalysisEventType
  node_key?: string
  node_name?: string
  status: AnalysisEventStatus
  message: string
  duration_ms?: number
  source_label?: string
  progress?: number
  payload?: Record<string, unknown>
  error_code?: string
  error_message?: string
  timestamp: string
}

export interface StreamHandlers {
  onEvent: (event: AnalysisStreamEvent) => void
  onError: (error: Error) => void
  onClose: () => void
}

export interface StreamController {
  abort: () => void
}
