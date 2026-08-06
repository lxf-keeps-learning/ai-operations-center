<script setup lang="ts">
import { computed, ref } from 'vue'

type SessionStatus = 'running' | 'success' | 'failed'

interface PlatformSession {
  id: string
  title: string
  agent: string
  channel: string
  status: SessionStatus
  runs: number
  tokens: string
  updatedAt: string
}

const activeTab = ref<'overview' | 'usage'>('overview')
const selectedFilter = ref<'all' | SessionStatus>('all')

const sessions: PlatformSession[] = [
  {
    id: 'sess_20260806_8c1a',
    title: '本质安全报告追问',
    agent: 'operation-supervisor',
    channel: 'Web Console',
    status: 'running',
    runs: 4,
    tokens: '12.4k',
    updatedAt: '刚刚',
  },
  {
    id: 'sess_20260806_41fd',
    title: '设备维护异常分析',
    agent: 'maintenance-agent',
    channel: 'Runtime API',
    status: 'success',
    runs: 7,
    tokens: '28.6k',
    updatedAt: '8 分钟前',
  },
  {
    id: 'sess_20260806_0b72',
    title: '生产运营日报汇总',
    agent: 'operation-supervisor',
    channel: 'Cron',
    status: 'success',
    runs: 1,
    tokens: '8.1k',
    updatedAt: '26 分钟前',
  },
  {
    id: 'sess_20260805_f320',
    title: '安全风险建议生成',
    agent: 'safety-agent',
    channel: 'Web Console',
    status: 'failed',
    runs: 3,
    tokens: '4.8k',
    updatedAt: '昨天 18:42',
  },
]

const filteredSessions = computed(() => {
  if (selectedFilter.value === 'all') return sessions
  return sessions.filter((session) => session.status === selectedFilter.value)
})

function statusLabel(status: SessionStatus) {
  return { running: '运行中', success: '已完成', failed: '失败' }[status]
}

function statusClass(status: SessionStatus) {
  return `session-status--${status}`
}
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
        <span class="muted-label">2026 年 8 月 6 日</span>
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
        <article class="metric-card">
          <div class="metric-card__top"><span class="metric-icon metric-icon--blue">⌁</span><span class="metric-change metric-change--down">↘ -12.8%</span></div>
          <span class="metric-label">今日请求</span>
          <strong>128</strong>
          <div class="sparkline sparkline--blue"><i /><i /><i /><i /><i /><i /><i /></div>
        </article>
        <article class="metric-card">
          <div class="metric-card__top"><span class="metric-icon metric-icon--purple">#</span><span class="metric-change metric-change--up">↗ +8.4%</span></div>
          <span class="metric-label">今日 Token</span>
          <strong>184.6k</strong>
          <small>输入 / 输出</small>
          <div class="sparkline sparkline--purple"><i /><i /><i /><i /><i /><i /><i /></div>
        </article>
        <article class="metric-card">
          <div class="metric-card__top"><span class="metric-icon metric-icon--green">$</span><span class="metric-change">本月</span></div>
          <span class="metric-label">今日费用</span>
          <strong class="metric-card__pending">待计算</strong>
          <small>已记录 Token，待接入模型价格表</small>
          <div class="sparkline sparkline--green"><i /><i /><i /><i /><i /><i /><i /></div>
        </article>
        <article class="metric-card">
          <div class="metric-card__top"><span class="metric-icon metric-icon--orange">♙</span><span class="metric-change">18 个 Agent</span></div>
          <span class="metric-label">运行中 Agent</span>
          <strong>3 <em>/ 18</em></strong>
          <div class="metric-progress"><span style="width: 17%" /></div>
        </article>
        <article class="metric-card">
          <div class="metric-card__top"><span class="metric-icon metric-icon--cyan">◉</span><span class="metric-change">4 个渠道</span></div>
          <span class="metric-label">在线 Channel</span>
          <strong>4 <em>/ 4</em></strong>
          <div class="metric-progress metric-progress--cyan"><span style="width: 100%" /></div>
        </article>
      </section>

      <section class="health-panel panel">
        <div class="panel-heading">
          <div><span class="section-icon">▣</span><h2>系统健康</h2></div>
          <span class="health-summary"><span class="status-dot" /> 所有核心服务正常</span>
        </div>
        <div class="health-grid">
          <div class="health-card"><span class="health-card__icon">◷</span><div><span>运行时间</span><strong>1d 18h 21m</strong></div></div>
          <div class="health-card"><span class="health-card__icon">▤</span><div><span>数据库</span><strong class="health-ok">已连接</strong></div></div>
          <div class="health-card"><span class="health-card__icon">⌁</span><div><span>Provider</span><strong class="health-ok">活跃</strong></div></div>
          <div class="health-card"><span class="health-card__icon">⚒</span><div><span>工具</span><strong>43</strong></div></div>
          <div class="health-card"><span class="health-card__icon">▣</span><div><span>Session</span><strong>4,994</strong></div></div>
          <div class="health-card"><span class="health-card__icon">♧</span><div><span>客户端</span><strong>4</strong></div></div>
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
          <div v-for="session in filteredSessions" :key="session.id" class="session-table__row">
            <div class="session-name"><strong>{{ session.title }}</strong><small>{{ session.id }}</small></div>
            <span class="session-agent">{{ session.agent }}</span>
            <span class="session-channel">{{ session.channel }}</span>
            <span>{{ session.runs }}</span>
            <span>{{ session.tokens }}</span>
            <span class="session-status" :class="statusClass(session.status)"><span class="status-dot" />{{ statusLabel(session.status) }}</span>
            <span class="session-time">{{ session.updatedAt }}</span>
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
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-bottom: 28px;
}

.metric-card,
.panel {
  background: #091229;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
}

.metric-card {
  min-height: 166px;
  overflow: hidden;
  padding: 17px 18px 0;
  position: relative;
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
