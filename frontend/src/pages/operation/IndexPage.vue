<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { marked } from 'marked'

import type { OperationAnalyzeParams } from '@/api/operation'
import { buildRequestKey, useOperationStore } from '@/stores/operation'

const store = useOperationStore()
const route = useRoute()
const router = useRouter()

const domainLabel: Record<string, string> = {
  safety: '本质安全',
  maintenance: '设备运维',
  business: '经营改善',
  capability: '能力提升',
}

const tabLabelByKey: Record<string, Record<string, string>> = {
  business: {
    credential: '经营指标',
    analysis: '客户分析',
    iot: '履约改善',
  },
  capability: {
    credential: '人员持证',
    analysis: '人效分析',
    iot: '物联接入',
  },
}
const timeDimensionApiMap: Record<string, string> = {
  日维度: 'day',
  周维度: 'week',
  月维度: 'month',
  季维度: 'quarter',
  年维度: 'year',
}
const timeDimensionLabelMap: Record<string, string> = {
  day: '日维度',
  week: '周维度',
  month: '月维度',
  quarter: '季维度',
  year: '年维度',
}

const queryDomain = computed(() => {
  return normalizeDomain(queryValue('domain') || queryValue('panel') || 'safety')
})
const queryTimeDim = computed(() => normalizeTimeDimension(queryValue('time_dimension') || 'month'))
const queryDate = computed(() => queryValue('date'))
const queryCategory = computed(() => queryValue('category'))
const queryTabKey = computed(() => queryValue('tab'))
const activeDomain = computed(() => domainLabel[queryDomain.value] || '本质安全')
const activeTab = computed(() => {
  const directTab = queryValue('active_tab')
  if (directTab) {
    return directTab
  }

  const tabKey = queryTabKey.value
  return tabLabelByKey[queryDomain.value]?.[tabKey] || activeDomain.value
})
const analysisParams = computed<OperationAnalyzeParams>(() => ({
  trigger_type: 'tab_analysis',
  domain: queryDomain.value,
  active_tab: activeTab.value,
  time_dimension: queryTimeDim.value,
  date: queryDate.value,
}))
const analysisKey = computed(() => buildRequestKey(analysisParams.value))
const hasResult = computed(() => store.result !== null && store.currentKey === analysisKey.value)
const canDownload = computed(() => hasResult.value && Boolean(store.result?.summary))
const reportDownloadFilename = computed(() => {
  const fileDate = queryDate.value || new Date().toISOString().slice(0, 10)
  return `运营分析报告_${safeFilePart(activeDomain.value)}_${safeFilePart(fileDate)}.md`
})
const reportDownloadHref = computed(() => {
  if (!canDownload.value) {
    return undefined
  }

  return `data:text/markdown;charset=utf-8,${encodeURIComponent(reportDownloadContent())}`
})
const displayParams = computed(() => {
  return [
    activeTab.value,
    timeDimensionLabel(queryTimeDim.value),
    queryDate.value,
    queryCategory.value,
  ].filter(Boolean)
})

const pageTitle = computed(() => `${activeDomain.value} — AI 运营分析诊断`)

function renderMarkdown(text: string): string {
  return marked.parse(normalizeReportMarkdown(text), { async: false, gfm: true }) as string
}

function normalizeReportMarkdown(text: string): string {
  return text
    .replace(/\r\n/g, '\n')
    .replace(/^##\s*运营分析(?:报告|结论)\s*\n+/u, '')
    .replace(/</g, '&lt;')
}

function startAnalysis() {
  void store.analyze(analysisParams.value, analysisKey.value)
}

function reportDownloadContent(): string {
  if (!store.result) {
    return ''
  }

  return [
    store.result.summary,
    '',
    `Trace：${store.result.trace_id}`,
    `状态：${store.result.status}`,
  ].join('\n')
}

function guardDownload(event: MouseEvent) {
  if (!canDownload.value) {
    event.preventDefault()
  }
}

async function ensureRouteAnalysis() {
  if (store.loading && store.currentKey === analysisKey.value) {
    return
  }

  if (store.loading && store.currentKey && store.currentKey !== analysisKey.value) {
    const ok = window.confirm(
      '上一份运营分析报告还没有生成完成，是否按当前新条件重新生成？',
    )
    if (!ok) {
      await restoreCurrentAnalysisRoute()
      return
    }

    startAnalysis()
    return
  }

  if (store.currentKey !== analysisKey.value || !store.result) {
    startAnalysis()
  }
}

async function restoreCurrentAnalysisRoute() {
  if (!store.currentParams) {
    return
  }

  await router.replace({
    path: '/operation',
    query: paramsToQuery(store.currentParams),
  })
}

function paramsToQuery(params: OperationAnalyzeParams): Record<string, string> {
  const query: Record<string, string> = {}
  for (const key of ['domain', 'active_tab', 'time_dimension', 'date'] as const) {
    const value = params[key]
    if (value) {
      query[key] = value
    }
  }
  return query
}

function queryValue(key: string): string {
  const value = route.query[key]
  if (Array.isArray(value)) {
    return value[0] || ''
  }
  return value || ''
}

function normalizeDomain(value: string): string {
  return value in domainLabel ? value : 'safety'
}

function normalizeTimeDimension(value: string): string {
  return timeDimensionApiMap[value] || value
}

function timeDimensionLabel(value: string): string {
  return timeDimensionLabelMap[value] || value
}

function safeFilePart(value: string): string {
  return value.replace(/[\\/:*?"<>|\s]+/g, '_').replace(/^_+|_+$/g, '') || 'report'
}

watch(
  analysisKey,
  () => {
    void ensureRouteAnalysis()
  },
  { immediate: true },
)
</script>

<template>
  <div class="operation-page">
    <div class="operation-page__header">
      <h1>运营分析</h1>
      <p class="page-subtitle">{{ pageTitle }}</p>
    </div>

    <div class="operation-page__actions">
      <button
        class="btn-analyze"
        :disabled="store.loading"
        @click="startAnalysis"
      >
        {{ store.loading ? '分析中...' : '分析' }}
      </button>
      <button
        class="btn-download"
        :disabled="!canDownload"
        type="button"
        @click="downloadReport"
      >
        一键下载报告
      </button>
      <div v-if="displayParams.length" class="operation-page__params">
        <span v-for="item in displayParams" :key="item" class="param-tag">{{ item }}</span>
      </div>
    </div>

    <p v-if="store.error" class="operation-error">{{ store.error }}</p>

    <!-- 分析过程展示 -->
    <div v-if="store.loading" class="operation-progress">
      <div class="progress-card">
        <h3>分析进行中 — {{ activeDomain }}</h3>
        <div class="step-list">
          <div
            v-for="(step, i) in store.steps"
            :key="i"
            class="step-item"
            :class="{
              'step-item--past': i < store.currentStep,
              'step-item--current': i === store.currentStep,
              'step-item--future': i > store.currentStep,
            }"
          >
            <span class="step-icon">
              <span v-if="i < store.currentStep" class="step-dot step-dot--done">✓</span>
              <span v-else-if="i === store.currentStep" class="step-dot step-dot--active" />
              <span v-else class="step-dot step-dot--pending" />
            </span>
            <span class="step-label" :class="{ 'step-label--active': i === store.currentStep }">
              {{ step }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 分析结果 -->
    <div v-if="hasResult" class="operation-result">
      <div class="result-section result-section--summary">
        <h2>AI 运营分析结论 — {{ activeDomain }}</h2>
        <div class="markdown-content" v-html="renderMarkdown(store.result!.summary)" />
      </div>

      <div v-if="store.result!.advice_items.length" class="result-section">
        <h2>建议动作</h2>
        <div v-for="(item, i) in store.result!.advice_items" :key="i" class="advice-card">
          <div class="advice-card__header">
            <span class="advice-priority" :class="`advice-priority--${(item.priority as string || 'P2').toLowerCase()}`">
              {{ item.priority || 'P2' }}
            </span>
            <strong>{{ item.title }}</strong>
          </div>
          <p class="advice-card__action">{{ item.action }}</p>
          <p v-if="item.owner_role" class="advice-card__meta">负责人：{{ item.owner_role }}</p>
          <p v-if="item.expected_result" class="advice-card__meta">预期：{{ item.expected_result }}</p>
        </div>
      </div>

      <div v-if="store.result!.evidence.length" class="result-section">
        <h2>数据依据</h2>
        <div class="evidence-list">
          <div v-for="(ev, i) in store.result!.evidence" :key="i" class="evidence-item">
            <span class="evidence-source">{{ ev.source }}</span>
            <span class="evidence-desc">{{ ev.description }}</span>
          </div>
        </div>
      </div>

      <div class="result-meta">
        <span>状态：{{ store.result!.status }}</span>
        <span>Trace：<code>{{ store.result!.trace_id }}</code></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.operation-page {
  max-width: 960px;
}

.operation-page__header h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0 0 4px;
}

.page-subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0 0 24px;
}

.operation-page__actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}

.operation-page__params {
  display: flex;
  gap: 8px;
}

.param-tag {
  background: #f1f5f9;
  border-radius: 4px;
  color: var(--color-text-muted);
  font-size: 13px;
  padding: 4px 10px;
}

.btn-analyze {
  align-items: center;
  background: #0f172a;
  border: none;
  border-radius: 8px;
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  font-size: 15px;
  font-weight: 800;
  justify-content: center;
  min-height: 42px;
  padding: 0 28px;
}

.btn-download {
  align-items: center;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: var(--color-heading);
  cursor: pointer;
  display: inline-flex;
  font-size: 14px;
  font-weight: 800;
  justify-content: center;
  min-height: 42px;
  padding: 0 20px;
}

.btn-analyze:disabled,
.btn-download:disabled {
  cursor: wait;
  opacity: 0.6;
}

.btn-download:disabled {
  cursor: not-allowed;
}

.operation-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  font-size: 14px;
  margin-bottom: 20px;
  padding: 12px 16px;
}

/* ── 分析进度展示 ── */
.operation-progress {
  margin-bottom: 24px;
}

.progress-card {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 24px;
}

.progress-card h3 {
  color: var(--color-heading);
  font-size: 16px;
  margin: 0 0 16px;
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.step-item {
  align-items: center;
  display: flex;
  gap: 12px;
  min-height: 40px;
  padding: 6px 0;
}

.step-icon {
  align-items: center;
  display: flex;
  flex-shrink: 0;
  height: 24px;
  justify-content: center;
  width: 24px;
}

.step-dot {
  border-radius: 50%;
  display: block;
}

.step-dot--done {
  align-items: center;
  background: #166534;
  color: #ffffff;
  display: flex;
  font-size: 11px;
  font-weight: 800;
  height: 20px;
  justify-content: center;
  width: 20px;
}

.step-dot--active {
  animation: pulse 1.5s infinite;
  background: #6366f1;
  height: 14px;
  width: 14px;
}

.step-dot--pending {
  background: #e2e8f0;
  height: 10px;
  width: 10px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}

.step-label {
  color: var(--color-text-muted);
  font-size: 14px;
}

.step-label--active {
  color: var(--color-heading);
  font-weight: 700;
}

.step-item--past .step-label {
  color: #166534;
}

/* ── 结果区域 ── */
.result-section {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 20px;
  padding: 24px;
}

.result-section h2 {
  color: var(--color-heading);
  font-size: 18px;
  margin: 0 0 16px;
}

.markdown-content {
  font-size: 15px;
  line-height: 1.8;
}

.markdown-content h3 {
  color: var(--color-heading);
  font-size: 17px;
  margin: 24px 0 12px;
}

.markdown-content h4 {
  color: var(--color-heading);
  font-size: 15px;
  margin: 20px 0 10px;
}

.markdown-content table {
  border-collapse: collapse;
  font-size: 14px;
  margin: 12px 0;
  width: 100%;
}

.markdown-content td,
.markdown-content th {
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
  text-align: left;
}

.markdown-content th {
  background: #f8fafc;
  font-weight: 800;
}

.markdown-content ul,
.markdown-content ol {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-content li {
  margin: 4px 0;
}

.markdown-content p {
  margin: 8px 0;
}

.markdown-content strong {
  font-weight: 800;
}

.markdown-content code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  padding: 2px 6px;
}

.markdown-content blockquote {
  border-left: 4px solid #6366f1;
  color: var(--color-text-muted);
  margin: 12px 0;
  padding: 8px 16px;
}

.advice-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;
  padding: 16px;
}

.advice-card__header {
  align-items: center;
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
}

.advice-priority {
  border-radius: 4px;
  font-size: 11px;
  font-weight: 800;
  padding: 2px 8px;
}

.advice-priority--p0 { background: #fef2f2; color: #991b1b; }
.advice-priority--p1 { background: #fffbeb; color: #854d0e; }
.advice-priority--p2 { background: #f0fdf4; color: #166534; }

.advice-card__action {
  color: var(--color-text);
  font-size: 14px;
  line-height: 1.6;
  margin: 0 0 6px;
}

.advice-card__meta {
  color: var(--color-text-muted);
  font-size: 13px;
  margin: 2px 0;
}

.evidence-list {
  display: grid;
  gap: 8px;
}

.evidence-item {
  align-items: flex-start;
  display: flex;
  font-size: 14px;
  gap: 12px;
  line-height: 1.6;
}

.evidence-source {
  background: #f1f5f9;
  border-radius: 4px;
  color: var(--color-text-muted);
  flex-shrink: 0;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  padding: 1px 8px;
}

.evidence-desc {
  color: var(--color-text);
}

.result-meta {
  border-top: 1px solid #e2e8f0;
  color: var(--color-text-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 13px;
  gap: 20px;
  padding-top: 16px;
}

.result-meta code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  padding: 1px 6px;
}
</style>
