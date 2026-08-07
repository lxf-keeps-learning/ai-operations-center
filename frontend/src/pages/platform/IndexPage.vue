<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getPlatformOverview, type PlatformOverview, type PlatformOverviewSession } from '@/api/platform'

import {
  buildOverviewMetricLinks,
  formatOverviewDate,
  formatOverviewMetric,
  formatOverviewTokens,
  formatOverviewUpdatedAt,
  getOverviewSessionStatus,
} from './indexPageModel'

type SessionStatus = 'running' | 'success' | 'failed'

const activeTab = ref<'overview' | 'usage'>('overview')
const selectedFilter = ref<'all' | SessionStatus>('all')
const overview = ref<PlatformOverview | null>(null)
const loading = ref(false)
const error = ref('')
const metricLinks = buildOverviewMetricLinks()
const todayLabel = formatOverviewDate(new Date())

const metrics = computed(() => overview.value?.metrics)
const sessions = computed(() => overview.value?.recent_sessions || [])

const filteredSessions = computed(() => {
  if (selectedFilter.value === 'all') return sessions.value
  return sessions.value.filter((session) => getOverviewSessionStatus(session.status) === selectedFilter.value)
})

const metricCards = computed(() => [
  { key: 'todayRequests', label: '今日请求数', value: metrics.value ? formatOverviewMetric(metrics.value.today_requests) : '—', detail: '按本地日统计', icon: '⌁', tone: 'blue', link: metricLinks.todayRequests },
  { key: 'runningTasks', label: '运行中任务', value: metrics.value ? formatOverviewMetric(metrics.value.running_tasks) : '—', detail: 'queued + running', icon: '◷', tone: 'orange', link: metricLinks.runningTasks },
  { key: 'pendingMessages', label: '待处理消息', value: metrics.value ? formatOverviewMetric(metrics.value.pending_messages) : '—', detail: '待复核与重新打开', icon: '▱', tone: 'cyan', link: metricLinks.pendingMessages },
  { key: 'failedTasks', label: '失败任务', value: metrics.value ? formatOverviewMetric(metrics.value.failed_tasks) : '—', detail: '今日失败 Session', icon: '!', tone: 'red', link: metricLinks.failedTasks },
  { key: 'tokenUsage', label: 'Token 用量', value: metrics.value ? formatOverviewTokens(metrics.value.total_tokens) : '—', detail: '今日 LLM Token', icon: '#', tone: 'purple', link: metricLinks.tokenUsage },
  { key: 'agentSuccessRate', label: 'Agent 成功率', value: metrics.value ? formatOverviewMetric(metrics.value.agent_success_rate, 'percent') : '—', detail: '已结束 Session', icon: '♙', tone: 'green', link: metricLinks.agentSuccessRate },
  { key: 'averageResponse', label: '平均响应时长', value: metrics.value ? formatOverviewMetric(metrics.value.average_response_ms, 'duration') : '—', detail: '已完成 Session', icon: '◌', tone: 'blue', link: metricLinks.averageResponse },
])

function statusLabel(status: string) {
  const normalized = getOverviewSessionStatus(status)
  if (normalized === 'running') return '运行中'
  if (normalized === 'success') return '已完成'
  if (normalized === 'cancelled') return '已取消'
  return '失败'
}

function statusClass(status: string) {
  return `session-status--${getOverviewSessionStatus(status)}`
}

function sessionTitle(session: PlatformOverviewSession) {
  return session.title || session.id
}

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    overview.value = await getPlatformOverview()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '概览数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadOverview())
</script>

<template>
  <div class="platform-dashboard">
    <section class="dashboard-heading">
      <div>
        <p class="eyebrow">AGENT PLATFORM</p>
        <h1>概览</h1>
        <p class="dashboard-heading__subtitle">Session、记忆与执行追踪的统一运行视图</p>
      </div>
      <div class="dashboard-heading__meta">
        <span class="live-pill"><span class="status-dot" /> 实时数据</span>
        <span class="muted-label">{{ todayLabel }}</span>
      </div>
    </section>

    <div class="dashboard-tabs" role="tablist" aria-label="概览视图">
      <button :class="{ 'is-active': activeTab === 'overview' }" @click="activeTab = 'overview'">
        概览
      </button>
      <button :class="{ 'is-active': activeTab === 'usage' }" @click="activeTab = 'usage'">
        用量
      </button>
    </div>

    <template v-if="activeTab === 'overview'">
      <section class="metric-grid">
        <RouterLink v-for="metric in metricCards" :key="metric.key" class="metric-card" :class="`metric-card--${metric.tone}`" :to="metric.link" :aria-label="`${metric.label}，点击查看明细`">
          <div class="metric-card__top"><span class="metric-icon">{{ metric.icon }}</span><span class="metric-change">查看明细 →</span></div>
          <span class="metric-label">{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.detail }}</small>
          <div class="sparkline"><i /><i /><i /><i /><i /><i /><i /></div>
        </RouterLink>
      </section>

      <div v-if="loading" class="overview-notice overview-notice--loading" role="status">正在加载概览数据...</div>
      <div v-if="error" class="overview-notice overview-notice--error" role="alert">
        <span>{{ error }}</span>
        <button type="button" @click="loadOverview">重试</button>
      </div>

      <section class="health-panel panel">
        <div class="panel-heading">
          <div><span class="section-icon">▣</span><h2>运行摘要</h2></div>
          <span class="health-summary"><span class="status-dot" :class="{ 'status-dot--error': error }" /> {{ error ? '概览接口异常' : loading ? '正在同步' : '数据已同步' }}</span>
        </div>
        <div class="health-grid">
          <div class="health-card"><span class="health-card__icon">◷</span><div><span>最近 Session</span><strong>{{ sessions.length }} 条</strong></div></div>
          <div class="health-card"><span class="health-card__icon">⌁</span><div><span>今日请求</span><strong>{{ metrics ? formatOverviewMetric(metrics.today_requests) : '—' }}</strong></div></div>
          <div class="health-card"><span class="health-card__icon">♙</span><div><span>运行中任务</span><strong>{{ metrics ? formatOverviewMetric(metrics.running_tasks) : '—' }}</strong></div></div>
          <div class="health-card"><span class="health-card__icon">#</span><div><span>LLM Token</span><strong>{{ metrics ? formatOverviewTokens(metrics.total_tokens) : '—' }}</strong></div></div>
          <div class="health-card"><span class="health-card__icon">◌</span><div><span>平均响应</span><strong>{{ metrics ? formatOverviewMetric(metrics.average_response_ms, 'duration') : '—' }}</strong></div></div>
          <div class="health-card"><span class="health-card__icon">✓</span><div><span>成功率</span><strong>{{ metrics ? formatOverviewMetric(metrics.agent_success_rate, 'percent') : '—' }}</strong></div></div>
        </div>
        <div class="runtime-strip">
          <span class="runtime-strip__label">运行时</span>
          <span class="runtime-tag"><span class="status-dot" /> python3 <b>Python 3.11</b></span>
          <span class="runtime-tag"><span class="status-dot" /> node <b>v22.14.0</b></span>
          <span class="runtime-tag"><span class="status-dot" /> mysql <b>8.0</b></span>
          <span class="runtime-tag runtime-tag--warn"><span class="status-dot" /> LangGraph Store <b>Postgres</b></span>
        </div>
      </section>

      <section class="sessions-panel panel">
        <div class="panel-heading panel-heading--sessions">
          <div><span class="section-icon">◷</span><h2>最近 Session</h2></div>
          <div class="session-filters">
            <button :class="{ 'is-active': selectedFilter === 'all' }" @click="selectedFilter = 'all'">全部</button>
            <button :class="{ 'is-active': selectedFilter === 'running' }" @click="selectedFilter = 'running'">运行中</button>
            <button :class="{ 'is-active': selectedFilter === 'failed' }" @click="selectedFilter = 'failed'">失败</button>
          </div>
        </div>
        <div class="session-table">
          <div class="session-table__row session-table__row--head"><span>SESSION</span><span>AGENT</span><span>CHANNEL</span><span>RUNS</span><span>TOKENS</span><span>状态</span><span>更新时间</span></div>
          <div v-if="loading && !overview" class="session-empty">正在加载 Session...</div>
          <div v-else-if="!filteredSessions.length" class="session-empty">暂无符合条件的 Session</div>
          <div v-for="session in filteredSessions" :key="session.id" class="session-table__row">
            <RouterLink class="session-name" :to="{ path: '/platform/sessions', query: { session_id: session.id } }"><strong>{{ sessionTitle(session) }}</strong><small>{{ session.id }}</small></RouterLink>
            <span class="session-agent">{{ session.agent || '-' }}</span>
            <span class="session-channel">{{ session.channel || '-' }}</span>
            <span>{{ session.runs }}</span>
            <span>{{ formatOverviewTokens(session.total_tokens) }}</span>
            <span class="session-status" :class="statusClass(session.status)"><span class="status-dot" />{{ statusLabel(session.status) }}</span>
            <span class="session-time">{{ formatOverviewUpdatedAt(session.updated_at) }}</span>
          </div>
        </div>
      </section>
    </template>

    <section v-else class="usage-placeholder panel">
      <span class="section-icon">#</span>
      <h2>用量分析</h2>
      <p>Token、成本和 Agent 调用趋势将在接入平台 Usage API 后展示。</p>
    </section>
  </div>
</template>

<style scoped>
.platform-dashboard {
  color: #e8eefc;
}

.dashboard-heading {
  align-items: flex-end;
  display: flex;
  justify-content: space-between;
  margin-bottom: 25px;
}

.eyebrow {
  color: #6977a0;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.2em;
  margin: 0 0 8px;
}

h1,
h2,
p {
  margin-top: 0;
}

h1 {
  color: #f4f7ff;
  font-size: 26px;
  letter-spacing: -0.03em;
  margin-bottom: 6px;
}

.dashboard-heading__subtitle,
.muted-label {
  color: #7f8ca9;
  font-size: 13px;
  margin-bottom: 0;
}

.dashboard-heading__meta,
.live-pill {
  align-items: center;
  display: flex;
  gap: 12px;
}

.live-pill {
  background: rgba(21, 199, 138, 0.1);
  border: 1px solid rgba(21, 199, 138, 0.2);
  border-radius: 999px;
  color: #7ce1bd;
  font-size: 11px;
  padding: 6px 10px;
}

.status-dot {
  background: #17c98e;
  border-radius: 50%;
  display: inline-block;
  height: 6px;
  width: 6px;
}

.dashboard-tabs {
  background: #0b1530;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  display: inline-flex;
  margin-bottom: 17px;
  padding: 3px;
}

.dashboard-tabs button,
.session-filters button {
  background: transparent;
  border: 0;
  border-radius: 6px;
  color: #7f8ca9;
  cursor: pointer;
  font-size: 12px;
  padding: 7px 16px;
}

.dashboard-tabs button.is-active,
.session-filters button.is-active {
  background: #1c2a4d;
  color: #f0f4ff;
}

.metric-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 28px;
}

.metric-card,
.panel {
  background: #091229;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
}

.metric-card {
  color: inherit;
  min-height: 166px;
  overflow: hidden;
  padding: 17px 18px 0;
  position: relative;
  text-decoration: none;
  transition: border-color 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease;
}

.metric-card:hover,
.metric-card:focus-visible {
  border-color: rgba(124, 141, 255, 0.7);
  box-shadow: 0 10px 24px rgba(1, 8, 26, 0.24);
  outline: none;
  transform: translateY(-2px);
}

.metric-card__top {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 13px;
}

.metric-icon,
.section-icon,
.health-card__icon {
  align-items: center;
  display: inline-flex;
  justify-content: center;
}

.metric-icon {
  background: #101d3b;
  border-radius: 8px;
  color: #aab6ff;
  font-size: 17px;
  height: 38px;
  width: 38px;
}

.metric-card--green .metric-icon { color: #5ed7aa; }
.metric-card--orange .metric-icon { color: #ffbe76; }
.metric-card--cyan .metric-icon { color: #72d9e3; }
.metric-card--red .metric-icon { color: #f27b89; }
.metric-card--purple .metric-icon { color: #b28cff; }
.metric-icon--green { color: #5ed7aa; }
.metric-icon--orange { color: #ffbe76; }
.metric-icon--cyan { color: #72d9e3; }

.metric-change {
  color: #63718e;
  font-size: 10px;
}

.metric-change--down { color: #f15d70; }
.metric-change--up { color: #5ed7aa; }

.metric-label {
  color: #7e8ca8;
  display: block;
  font-size: 12px;
  margin-bottom: 5px;
}

.metric-card strong {
  color: #f5f7ff;
  display: block;
  font-size: 25px;
  letter-spacing: -0.04em;
}

.metric-card strong em {
  color: #6f7d99;
  font-size: 13px;
  font-style: normal;
  font-weight: 500;
}

.metric-card strong.metric-card__pending {
  color: #f4bf79;
  font-size: 21px;
  letter-spacing: -0.02em;
}

.metric-card small {
  color: #566783;
  display: block;
  font-size: 10px;
  margin-top: 2px;
}

.sparkline {
  bottom: -3px;
  display: flex;
  gap: 3px;
  height: 28px;
  left: 18px;
  position: absolute;
  right: 18px;
}

.sparkline i {
  align-self: flex-end;
  background: #5f6eff;
  border-radius: 4px 4px 0 0;
  display: block;
  flex: 1;
  opacity: 0.72;
}

.sparkline i:nth-child(1) { height: 30%; }
.sparkline i:nth-child(2) { height: 58%; }
.sparkline i:nth-child(3) { height: 38%; }
.sparkline i:nth-child(4) { height: 82%; }
.sparkline i:nth-child(5) { height: 44%; }
.sparkline i:nth-child(6) { height: 67%; }
.sparkline i:nth-child(7) { height: 52%; }
.sparkline--purple i { background: #a078ff; }
.sparkline--green i { background: #42c99b; }

.metric-progress {
  background: #172342;
  border-radius: 99px;
  height: 5px;
  margin-top: 18px;
  overflow: hidden;
}

.metric-progress span {
  background: #ffb36b;
  border-radius: inherit;
  display: block;
  height: 100%;
}

.metric-progress--cyan span { background: #47cddd; }

.panel {
  margin-bottom: 22px;
  padding: 20px 22px;
}

.panel-heading {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 18px;
}

.panel-heading > div:first-child {
  align-items: center;
  display: flex;
  gap: 10px;
}

.section-icon {
  color: #93a0bd;
  font-size: 18px;
  width: 19px;
}

h2 {
  color: #e9efff;
  font-size: 16px;
  letter-spacing: -0.01em;
  margin-bottom: 0;
}

.health-summary {
  align-items: center;
  color: #75dab8;
  display: flex;
  font-size: 11px;
  gap: 8px;
}

.status-dot--error { background: #ef6478; }

.overview-notice {
  align-items: center;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  display: flex;
  font-size: 12px;
  justify-content: space-between;
  margin: -10px 0 22px;
  padding: 10px 13px;
}

.overview-notice--loading { background: rgba(85, 104, 194, 0.12); color: #aab8e4; }
.overview-notice--error { background: rgba(239, 100, 120, 0.1); border-color: rgba(239, 100, 120, 0.3); color: #f59aaa; }
.overview-notice button { background: transparent; border: 0; color: inherit; cursor: pointer; font-weight: 700; }

.health-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.health-card {
  align-items: center;
  background: #0d1730;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 9px;
  display: flex;
  gap: 12px;
  min-height: 66px;
  padding: 12px 14px;
}

.health-card__icon {
  background: #14203d;
  border-radius: 8px;
  color: #8b9abd;
  flex-shrink: 0;
  font-size: 16px;
  height: 34px;
  width: 34px;
}

.health-card span:not(.health-card__icon),
.health-card strong {
  display: block;
}

.health-card span:not(.health-card__icon) {
  color: #7987a3;
  font-size: 11px;
  margin-bottom: 4px;
}

.health-card strong {
  color: #dfe7fb;
  font-size: 14px;
}

.health-card .health-ok {
  color: #64d7b0;
}

.runtime-strip {
  align-items: center;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
  padding-top: 17px;
}

.runtime-strip__label {
  color: #667592;
  font-size: 11px;
  margin-right: 3px;
  text-transform: uppercase;
}

.runtime-tag {
  align-items: center;
  background: #0d1730;
  border-radius: 5px;
  color: #c8d2e8;
  display: inline-flex;
  font-size: 11px;
  gap: 7px;
  padding: 7px 9px;
}

.runtime-tag b {
  color: #70809f;
  font-weight: 500;
}

.runtime-tag--warn .status-dot { background: #f2aa5d; }

.session-filters {
  background: #0d1730;
  border-radius: 7px;
  display: flex;
  gap: 2px;
  padding: 3px;
}

.session-filters button {
  font-size: 11px;
  padding: 5px 10px;
}

.session-table {
  overflow-x: auto;
}

.session-table__row {
  align-items: center;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  color: #b3bfd6;
  display: grid;
  font-size: 12px;
  gap: 14px;
  grid-template-columns: minmax(210px, 1.7fr) minmax(145px, 1fr) minmax(115px, 0.9fr) 45px 70px 90px 82px;
  min-width: 900px;
  padding: 13px 4px;
}

.session-table__row--head {
  border-top: 0;
  color: #647391;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding-bottom: 10px;
  padding-top: 0;
}

.session-name strong,
.session-name small {
  display: block;
}

.session-name { text-decoration: none; }

.session-name strong {
  color: #e6ecfd;
  font-size: 12px;
  font-weight: 700;
}

.session-name small {
  color: #657492;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10px;
  margin-top: 4px;
}

.session-agent {
  color: #9aa8c4;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
}

.session-channel,
.session-time {
  color: #7d8ca9;
}

.session-status {
  align-items: center;
  display: inline-flex;
  font-size: 11px;
  gap: 7px;
}

.session-status--running { color: #75dcb9; }
.session-status--success { color: #91a0bd; }
.session-status--failed { color: #f27b89; }
.session-status--failed .status-dot { background: #ef6478; }
.session-status--success .status-dot { background: #6f809e; }
.session-status--cancelled { color: #d69b68; }
.session-status--cancelled .status-dot { background: #d69b68; }

.session-empty {
  color: #71809b;
  padding: 44px 12px;
  text-align: center;
}

.usage-placeholder {
  align-items: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 320px;
  text-align: center;
}

.usage-placeholder .section-icon {
  font-size: 28px;
  margin-bottom: 14px;
}

.usage-placeholder p {
  color: #7e8ca8;
  font-size: 13px;
  margin-bottom: 0;
}

@media (max-width: 1100px) {
  .metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .dashboard-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }

  .metric-grid,
  .health-grid {
    grid-template-columns: 1fr;
  }

  .panel {
    padding-left: 15px;
    padding-right: 15px;
  }

  .panel-heading--sessions {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
}
</style>
