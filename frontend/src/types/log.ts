export interface LogEntry {
  traceId: string
  level: string
  path: string
  method: string
  status: number
  durationMs: number
  time: string
}

export interface LlmUsageLog {
  traceId: string
  provider: string
  model: string
  inputTokens: number
  outputTokens: number
  totalTokens: number
  durationMs: number
  success: boolean
  errorMessage?: string
}
