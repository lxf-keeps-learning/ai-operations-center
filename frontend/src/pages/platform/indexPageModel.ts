export type OverviewMetricLink = {
  path: string
  query: Record<string, string>
}

export interface OverviewMetricLinks {
  todayRequests: OverviewMetricLink
  runningTasks: OverviewMetricLink
  pendingMessages: OverviewMetricLink
  failedTasks: OverviewMetricLink
  tokenUsage: OverviewMetricLink
  agentSuccessRate: OverviewMetricLink
  averageResponse: OverviewMetricLink
}

export type OverviewSessionStatus = 'running' | 'success' | 'failed' | 'cancelled' | 'other'

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function localDate(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function formatOverviewDate(date: Date) {
  return `${date.getFullYear()} 年 ${date.getMonth() + 1} 月 ${date.getDate()} 日`
}

function compactDecimal(value: number) {
  return value.toFixed(1).replace(/\.0$/, '')
}

export function buildOverviewMetricLinks(now = new Date()): OverviewMetricLinks {
  const date = localDate(now)
  return {
    todayRequests: { path: '/platform/sessions', query: { date_from: date, date_to: date } },
    runningTasks: { path: '/platform/sessions', query: { status: 'queued,running' } },
    pendingMessages: { path: '/platform/messages', query: { status: 'awaiting_review' } },
    failedTasks: { path: '/platform/sessions', query: { status: 'failed', date_from: date, date_to: date } },
    tokenUsage: { path: '/platform/traces', query: { span_type: 'llm', date_from: date, date_to: date } },
    agentSuccessRate: { path: '/platform/agents', query: {} },
    averageResponse: { path: '/platform/sessions', query: { status: 'success,failed' } },
  }
}

export function formatOverviewTokens(value: number) {
  if (value >= 1_000_000) return `${compactDecimal(value / 1_000_000)}m`
  if (value >= 1_000) return `${compactDecimal(value / 1_000)}k`
  return String(Math.round(value))
}

export function formatOverviewMetric(value: number, kind: 'number' | 'percent' | 'duration' = 'number') {
  if (kind === 'percent') return `${compactDecimal(value * 100)}%`
  if (kind === 'duration') return value >= 1_000 ? `${compactDecimal(value / 1_000)} s` : `${Math.round(value)} ms`
  return String(Math.round(value))
}

export function formatOverviewUpdatedAt(value: string | null | undefined) {
  if (!value) return '-'
  return value.slice(0, 16).replace('T', ' ')
}

export function getOverviewSessionStatus(status: string): OverviewSessionStatus {
  if (status === 'created' || status === 'queued' || status === 'running' || status === 'cancel_requested') return 'running'
  if (status === 'success') return 'success'
  if (status === 'failed') return 'failed'
  if (status === 'cancelled') return 'cancelled'
  return 'other'
}
