<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { createOperationAnalyzePayload } from '@/adapters/operationContext'
import RuntimeChatPanel from '@/components/RuntimeChatPanel.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAppStore } from '@/stores/app'
import type { AgentAnalyzeRequest } from '@/types/api'

const appStore = useAppStore()
const analyzePayload = ref<AgentAnalyzeRequest>(createOperationAnalyzePayload())

const capabilityCards = [
  {
    title: '运营分析',
    desc: '汇总 KPI、告警、工单和能耗上下文，输出异常原因和关注优先级。',
    meta: 'Operation Agent',
  },
  {
    title: '隐患研判',
    desc: '围绕隐患对象生成风险评级、整改建议和可追踪分析依据。',
    meta: 'HiddenRisk Agent',
  },
  {
    title: '流式输出',
    desc: 'REST 创建任务，SSE 渲染 start、progress、token、done 全流程。',
    meta: 'Runtime SSE',
  },
]

const directoryItems = [
  ['api', 'REST / SSE 接口封装'],
  ['adapters', '页面上下文适配'],
  ['components', '公共展示组件'],
  ['hooks', '组合式复用逻辑'],
  ['layouts', '应用布局'],
  ['pages', '路由页面组合'],
  ['router', '前端路由'],
  ['stores', 'Pinia 状态'],
  ['types', 'TypeScript DTO'],
  ['utils', '通用工具'],
]

const apiItems = [
  ['GET', '/api/v1/health', '服务健康检查'],
  ['POST', '/api/v1/agent/analyze', '发起 AI 分析'],
  ['GET', '/api/v1/agent/stream', '订阅 SSE 输出'],
  ['GET', '/api/v1/conversations', '查询会话列表'],
  ['POST', '/api/v1/feedback', '提交用户反馈'],
]

const healthTone = computed(() => {
  if (appStore.apiStatus === 'online') {
    return 'success'
  }

  if (appStore.apiStatus === 'offline') {
    return 'danger'
  }

  if (appStore.apiStatus === 'checking') {
    return 'info'
  }

  return 'warning'
})

const healthLabel = computed(() => {
  if (appStore.apiStatus === 'online') {
    return '后端在线'
  }

  if (appStore.apiStatus === 'offline') {
    return '后端未连接'
  }

  if (appStore.apiStatus === 'checking') {
    return '检测中'
  }

  return '等待检测'
})

const healthDetails = computed(() => {
  if (!appStore.health) {
    return [
      ['Database', '-'],
      ['Redis', '-'],
      ['LLM', '-'],
    ]
  }

  return [
    ['Database', appStore.health.database || '-'],
    ['Redis', appStore.health.redis || '-'],
    ['LLM', appStore.health.llm || '-'],
  ]
})

const payloadText = computed(() => JSON.stringify(analyzePayload.value, null, 2))

function refreshPayload() {
  analyzePayload.value = createOperationAnalyzePayload()
}

onMounted(() => {
  void appStore.checkHealth()
})
</script>

<template>
  <section class="hero">
    <div class="hero__content">
      <StatusBadge :tone="healthTone" :label="healthLabel" />
      <h1>IOC AI Agent 前端工作台</h1>
      <p>
        Vue3、Vite、TypeScript 已就位，前端通过统一 API 层连接 FastAPI Runtime，
        面向运营分析、隐患研判和流式 AI 输出继续扩展。
      </p>
      <div class="hero__actions">
        <button class="button button--primary" type="button" :disabled="appStore.loading" @click="appStore.checkHealth">
          {{ appStore.loading ? '检测中' : '检测后端' }}
        </button>
        <button class="button" type="button" @click="refreshPayload">刷新上下文</button>
      </div>
      <p v-if="appStore.errorMessage" class="hero__error">{{ appStore.errorMessage }}</p>
    </div>

    <div class="runtime-panel" aria-label="运行状态">
      <div class="runtime-panel__head">
        <span>Runtime</span>
        <strong>{{ appStore.health?.status || 'UNKNOWN' }}</strong>
      </div>
      <dl>
        <template v-for="[name, value] in healthDetails" :key="name">
          <dt>{{ name }}</dt>
          <dd>{{ value }}</dd>
        </template>
      </dl>
    </div>
  </section>

  <section class="section-grid">
    <article v-for="card in capabilityCards" :key="card.title" class="capability-card">
      <span>{{ card.meta }}</span>
      <h2>{{ card.title }}</h2>
      <p>{{ card.desc }}</p>
    </article>
  </section>

  <section class="workspace-grid">
    <div class="workspace-panel">
      <div class="panel-title">
        <span>前端目录</span>
        <strong>src</strong>
      </div>
      <ul class="directory-list">
        <li v-for="[name, desc] in directoryItems" :key="name">
          <code>{{ name }}</code>
          <span>{{ desc }}</span>
        </li>
      </ul>
    </div>

    <div class="workspace-panel">
      <div class="panel-title">
        <span>Runtime API</span>
        <strong>/api/v1</strong>
      </div>
      <ul class="api-list">
        <li v-for="[method, path, desc] in apiItems" :key="path">
          <b>{{ method }}</b>
          <code>{{ path }}</code>
          <span>{{ desc }}</span>
        </li>
      </ul>
    </div>
  </section>

  <section class="payload-section">
    <div class="panel-title">
      <span>页面上下文</span>
      <strong>Analyze Payload</strong>
    </div>
    <pre>{{ payloadText }}</pre>
  </section>

  <section class="chat-section">
    <RuntimeChatPanel />
  </section>
</template>

<style scoped>
.hero {
  align-items: stretch;
  display: grid;
  gap: 24px;
  grid-template-columns: minmax(0, 1fr) 360px;
  margin-bottom: 24px;
}

.hero__content {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 34px;
}

.hero h1 {
  color: var(--color-heading);
  font-size: clamp(34px, 6vw, 58px);
  line-height: 1.05;
  margin: 22px 0 16px;
  max-width: 760px;
}

.hero p {
  color: var(--color-text-muted);
  font-size: 17px;
  line-height: 1.8;
  margin: 0;
  max-width: 780px;
}

.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 26px;
}

.hero__error {
  color: #b91c1c;
  font-size: 14px;
  margin-top: 16px;
}

.runtime-panel,
.workspace-panel,
.payload-section,
.capability-card {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.runtime-panel {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 26px;
}

.runtime-panel__head,
.panel-title {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.runtime-panel__head span,
.panel-title span {
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
}

.runtime-panel__head strong,
.panel-title strong {
  color: var(--color-heading);
  font-size: 18px;
}

.runtime-panel dl {
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr auto;
  margin: 36px 0 0;
}

.runtime-panel dt {
  color: var(--color-text-muted);
}

.runtime-panel dd {
  color: var(--color-heading);
  font-weight: 800;
  margin: 0;
}

.section-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 24px;
}

.capability-card {
  padding: 24px;
}

.capability-card span {
  color: #0369a1;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.capability-card h2 {
  color: var(--color-heading);
  font-size: 22px;
  margin: 12px 0 10px;
}

.capability-card p {
  color: var(--color-text-muted);
  line-height: 1.7;
  margin: 0;
}

.workspace-grid {
  display: grid;
  gap: 24px;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  margin-bottom: 24px;
}

.workspace-panel {
  padding: 24px;
}

.directory-list,
.api-list {
  display: grid;
  gap: 10px;
  list-style: none;
  margin: 22px 0 0;
  padding: 0;
}

.directory-list li,
.api-list li {
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: grid;
  gap: 12px;
  min-height: 48px;
  padding: 10px 12px;
}

.directory-list li {
  grid-template-columns: 96px 1fr;
}

.api-list li {
  grid-template-columns: 56px minmax(180px, 1fr) 120px;
}

.api-list b {
  color: #047857;
  font-size: 12px;
}

code {
  color: #334155;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}

.directory-list span,
.api-list span {
  color: var(--color-text-muted);
  font-size: 14px;
}

.payload-section {
  padding: 24px;
}

.payload-section pre {
  background: #101828;
  border-radius: 8px;
  color: #e0f2fe;
  font-size: 13px;
  line-height: 1.7;
  margin: 22px 0 0;
  overflow-x: auto;
  padding: 20px;
}

.button {
  align-items: center;
  background: #ffffff;
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  color: var(--color-heading);
  cursor: pointer;
  display: inline-flex;
  font-size: 15px;
  font-weight: 800;
  justify-content: center;
  min-height: 42px;
  padding: 0 16px;
}

.button:hover {
  border-color: #94a3b8;
}

.button:disabled {
  cursor: wait;
  opacity: 0.7;
}

.button--primary {
  background: #0f172a;
  border-color: #0f172a;
  color: #ffffff;
}

@media (max-width: 980px) {
  .hero,
  .workspace-grid,
  .section-grid {
    grid-template-columns: 1fr;
  }

  .api-list li {
    align-items: flex-start;
    grid-template-columns: 56px 1fr;
  }

  .api-list span {
    grid-column: 2;
  }
}

@media (max-width: 560px) {
  .hero__content,
  .runtime-panel,
  .workspace-panel,
  .payload-section,
  .capability-card {
    padding: 20px;
  }

  .hero h1 {
    font-size: 36px;
  }

  .directory-list li {
    align-items: flex-start;
    grid-template-columns: 1fr;
  }
}

.chat-section {
  margin-top: 24px;
}
</style>
