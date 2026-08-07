import assert from 'node:assert/strict'

import {
  buildOverviewMetricLinks,
  formatOverviewMetric,
  formatOverviewDate,
  formatOverviewTokens,
  formatOverviewUpdatedAt,
  getOverviewSessionStatus,
} from './indexPageModel.ts'

const links = buildOverviewMetricLinks(new Date(2026, 7, 7))
assert.equal(links.todayRequests.path, '/platform/sessions')
assert.equal(links.todayRequests.query.date_from, '2026-08-07')
assert.equal(links.todayRequests.query.date_to, '2026-08-07')
assert.equal(links.runningTasks.query.status, 'queued,running')
assert.equal(links.pendingMessages.path, '/platform/messages')
assert.equal(links.pendingMessages.query.status, 'awaiting_review')
assert.equal(links.failedTasks.query.status, 'failed')
assert.equal(links.failedTasks.query.date_from, '2026-08-07')
assert.equal(links.failedTasks.query.date_to, '2026-08-07')
assert.equal(links.tokenUsage.path, '/platform/traces')
assert.equal(links.tokenUsage.query.span_type, 'llm')
assert.equal(links.tokenUsage.query.date_from, '2026-08-07')
assert.equal(links.tokenUsage.query.date_to, '2026-08-07')
assert.equal(links.agentSuccessRate.path, '/platform/agents')
assert.equal(links.averageResponse.path, '/platform/sessions')
assert.equal(links.averageResponse.query.status, 'success,failed')

assert.equal(formatOverviewMetric(0), '0')
assert.equal(formatOverviewMetric(128), '128')
assert.equal(formatOverviewTokens(184600), '184.6k')
assert.equal(formatOverviewMetric(0.984, 'percent'), '98.4%')
assert.equal(formatOverviewMetric(1250, 'duration'), '1.3 s')
assert.equal(formatOverviewDate(new Date(2026, 7, 7)), '2026 年 8 月 7 日')
assert.equal(formatOverviewUpdatedAt('2026-08-07T10:20:30+08:00'), '2026-08-07 10:20')
assert.equal(getOverviewSessionStatus('queued'), 'running')
assert.equal(getOverviewSessionStatus('cancel_requested'), 'running')
assert.equal(getOverviewSessionStatus('success'), 'success')

console.log('platform overview page model checks passed')
