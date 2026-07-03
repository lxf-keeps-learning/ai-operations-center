import { request } from '@/utils/request'
import type { LogEntry, LlmUsageLog } from '@/types/log'

export async function getRecentLogs() {
  return request<LogEntry[]>('/logs/recent')
}

export async function getLlmUsageLogs() {
  return request<LlmUsageLog[]>('/logs/llm-usage')
}
