<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { AnalysisBasis, OperationAnalyzeParams, OperationResult } from '@/api/operation'
import { getRecordDetail, getDownloadUrl, listRecords, type AnalysisRecord, type AnalysisRecordDetail } from '@/api/records'
import { buildRequestKey, useOperationStore } from '@/stores/operation'
import ReportChatPanel from '@/components/ReportChatPanel.vue'
import { useAnalysisProgressStore } from '@/stores/analysisProgressStore'
import { renderSafeMarkdown } from '@/utils/markdown'

const store = useOperationStore()
const progressStore = useAnalysisProgressStore()
const route = useRoute()
const router = useRouter()

const domainLabel: Record<string, string> = {
  safety: '本质安全',
  maintenance: '设备运维',
  business: '经营改善',
  capability: '能力提升',
}
const timeDimensionLabelMap: Record<string, string> = {
  day: '日维度',
  week: '周维度',
  month: '月维度',
  quarter: '季维度',
  year: '年维度',
}
const timeDimensionApiMap: Record<string, string> = {
  '日维度': 'day',
  '周维度': 'week',
  '月维度': 'month',
  '季维度': 'quarter',
  '年维度': 'year',
}

const tabLabelByKey: Record<string, Record<string, string>> = {
  business: { credential: '经营指标', analysis: '客户分析', iot: '履约改善' },
  capability: { credential: '人员持证', analysis: '人效分析', iot: '物联接入' },
}

const domainTabs = [
  { key: 'safety', label: '本质安全' },
  { key: 'maintenance', label: '设备运维' },
  { key: 'business', label: '经营改善' },
  { key: 'capability', label: '能力提升' },
]

const records = ref<AnalysisRecord[]>([])
const selectedRecord = ref<AnalysisRecordDetail | null>(null)
const loadingRecords = ref(false)
const loadingDetail = ref(false)
const userSelected = ref(false)
const error = ref('')
const activeAnalysisParams = ref<OperationAnalyzeParams | null>(null)
const activeAnalysisKey = ref('')

onMounted(async () => {
  const shouldGenerate = queryValue('generate') === '1' && queryValue('source') === 'overview_ai'
  if (queryValue('generate') || queryValue('source')) {
    await clearGenerateIntent()
  }
  if (shouldGenerate) {
    // 从运营总览进入生成流程时，也要先加载当前领域的历史报告。
    // 否则 startRequestedAnalysis 后直接 return，左侧只剩生成中占位项。
    await fetchRecords()
    startRequestedAnalysis()
    return
  }
  await loadMatchingReport()
})

onUnmounted(() => {
  progressStore.cancelStream()
})

const queryDomain = computed(() => normalizeDomain(queryValue('domain') || queryValue('panel') || 'safety'))
const queryTimeDim = computed(() => normalizeTimeDimension(queryValue('time_dimension') || 'month'))
const queryDate = computed(() => queryValue('date'))
const queryCategory = computed(() => queryValue('category'))
const queryTabKey = computed(() => queryValue('tab'))
const activeDomain = computed(() => domainLabel[queryDomain.value] || '本质安全')
const activeTab = computed(() => {
  const directTab = queryValue('active_tab')
  if (directTab) return directTab
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
const canDownload = computed(() => Boolean(store.result?.summary))
const selectedRecordId = computed(() => selectedRecord.value?.id ?? null)
const selectedReportTitle = computed(() => selectedRecord.value?.report_name || '运营分析报告')
const chatReportId = computed(() => selectedRecordId.value)

const displayParams = computed(() => {
  return [
    activeTab.value === activeDomain.value ? '' : activeTab.value,
    timeDimensionLabel(queryTimeDim.value),
    queryDate.value,
    queryCategory.value,
  ].filter(Boolean)
})

const pageTitle = computed(() => `${activeDomain.value} — AI 运营分析诊断`)

function renderMarkdown(text: string): string {
  return renderSafeMarkdown(text, { stripOperationHeading: true })
}

function startRequestedAnalysis() {
  const params = { ...analysisParams.value, force_refresh: true }
  activeAnalysisParams.value = params
  activeAnalysisKey.value = buildRequestKey(params)
  selectedRecord.value = null
  userSelected.value = false
  progressStore.startStreamAnalysis(params)
}

async function clearGenerateIntent() {
  const query = { ...route.query }
  delete query.generate
  delete query.source
  await router.replace({ path: '/operation', query })
}

async function loadMatchingReport() {
  await fetchRecords()
  const match = matchingRecords.value[0]
  if (match) {
    await selectRecord(match.id, false)
    return
  }
  selectedRecord.value = null
  userSelected.value = false
}

function selectDomain(domain: string) {
  const query = { ...route.query }
  query.domain = domain
  query.active_tab = domainLabel[domain] || domain
  delete query.generate
  delete query.source
  delete query.tab
  void router.replace({ path: '/operation', query })
}

function downloadReport() {
  if (!canDownload.value || !store.result) return
  const fileDate = queryDate.value || new Date().toISOString().slice(0, 10)
  const filename = `运营分析报告_${safeFilePart(activeDomain.value)}_${safeFilePart(fileDate)}.md`
  const content = [
    store.result.summary,
    '',
    `Trace：${store.result.trace_id}`,
    `状态：${store.result.status}`,
  ].join('\n')
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

async function fetchRecords() {
  loadingRecords.value = true
  error.value = ''
  try {
    records.value = await listRecords({ domain: queryDomain.value, page_size: 50 })
    if (selectedRecord.value && selectedRecord.value.domain !== queryDomain.value) {
      selectedRecord.value = null
      userSelected.value = false
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载分析记录失败'
  } finally {
    loadingRecords.value = false
  }
}

async function selectRecord(id: number, markUserSelected = true) {
  if (progressStore.loading) {
    progressStore.cancelStream()
  }
  userSelected.value = markUserSelected
  loadingDetail.value = true
  error.value = ''
  try {
    selectedRecord.value = await getRecordDetail(id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载报告详情失败'
  } finally {
    loadingDetail.value = false
  }
}

function queryValue(key: string): string {
  const value = route.query[key]
  return Array.isArray(value) ? (value[0] || '') : (value || '')
}

function normalizeDomain(value: string): string {
  return value in domainLabel ? value : 'safety'
}

function normalizeTimeDimension(value: string): string {
  const normalized = timeDimensionApiMap[value] || value
  return normalized in timeDimensionLabelMap ? normalized : 'month'
}

function timeDimensionLabel(value: string): string {
  return timeDimensionLabelMap[value] || value
}

function safeFilePart(value: string): string {
  return value.replace(/[\\/:*?"<>|\s]+/g, '_').replace(/^_+|_+$/g, '') || 'report'
}

function formatRecordMeta(record: AnalysisRecord): string {
  const recordActiveTab = typeof record.page_context?.active_tab === 'string'
    ? record.page_context.active_tab
    : ''
  const domainText = domainLabel[record.domain] || record.domain
  const parts = [
    domainText,
    recordActiveTab === domainText ? '' : recordActiveTab,
    record.time_dimension ? timeDimensionLabel(record.time_dimension) : '',
    record.analysis_date || (record.created_at ? record.created_at.slice(0, 10) : ''),
  ].filter(Boolean)
  return parts.join(' / ')
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return iso.slice(0, 19).replace('T', ' ')
}

const domainRecords = computed(() => {
  const domain = queryDomain.value
  return records.value.filter(r => r.domain === domain)
})

const matchingRecords = computed(() => {
  return domainRecords.value.filter(recordMatchesCurrentParams)
})

const isGenerating = computed(() => {
  return (
    (progressStore.loading && progressStore.status === 'running')
    || (store.loading && store.currentKey === analysisKey.value)
  )
})

const pageError = computed(() => error.value || progressStore.error || store.error)

watch(analysisKey, () => {
  selectedRecord.value = null
  userSelected.value = false
  store.reset()
  void loadMatchingReport()
})

watch(
  () => store.result,
  async (newResult) => {
    if (newResult) {
      selectedRecord.value = null
      userSelected.value = false
      await fetchRecords()
      if (newResult.record_id) {
        await selectRecord(newResult.record_id, false)
        return
      }
      const matched = matchingRecords.value[0]
      if (matched) {
        await selectRecord(matched.id, false)
      }
    }
  },
)

watch(
  () => progressStore.report,
  (payload) => {
    if (!payload || !activeAnalysisParams.value) return
    store.applyStreamResult(
      normalizeStreamResult(payload),
      activeAnalysisParams.value,
      activeAnalysisKey.value || buildRequestKey(activeAnalysisParams.value),
    )
  },
)

watch(
  () => progressStore.error,
  (message) => {
    if (message) {
      store.applyStreamError(message)
    }
  },
)



function recordMatchesCurrentParams(record: AnalysisRecord): boolean {
  if (record.domain !== queryDomain.value) return false
  if ((record.time_dimension || '') !== queryTimeDim.value) return false
  if ((record.analysis_date || '') !== (queryDate.value || '')) return false
  const recordActiveTab = typeof record.page_context?.active_tab === 'string'
    ? record.page_context.active_tab
    : ''
  return (recordActiveTab || '') === (activeTab.value || '')
}

function normalizeStreamResult(payload: Record<string, unknown>): OperationResult {
  return {
    record_id: typeof payload.record_id === 'number' ? payload.record_id : null,
    trace_id: typeof payload.trace_id === 'string' ? payload.trace_id : '',
    status: typeof payload.status === 'string' ? payload.status : 'success',
    summary: typeof payload.summary === 'string' ? payload.summary : '',
    abnormal_items: toRecordList(payload.abnormal_items),
    risk_items: toRecordList(payload.risk_items),
    advice_items: toRecordList(payload.advice_items),
    evidence: toRecordList(payload.evidence),
    analysis_basis: normalizeAnalysisBasis(payload.analysis_basis),
    errors: toRecordList(payload.errors),
  }
}

function normalizeAnalysisBasis(value: unknown): AnalysisBasis {
  const basis = isRecord(value) ? value : {}
  return {
    schema_version: typeof basis.schema_version === 'string' ? basis.schema_version : '1.0',
    data_evidence: toRecordList(basis.data_evidence),
    knowledge_evidence: toRecordList(basis.knowledge_evidence),
    knowledge_status: typeof basis.knowledge_status === 'string' ? basis.knowledge_status : 'not_used',
    knowledge_note: typeof basis.knowledge_note === 'string' ? basis.knowledge_note : '本次常规报告未使用知识库依据。',
    facts: toRecordList(basis.facts),
    hypotheses: toRecordList(basis.hypotheses),
    assumptions: toStringList(basis.assumptions),
    verification_steps: toStringList(basis.verification_steps),
    reasoning_confidence: typeof basis.reasoning_confidence === 'number' ? basis.reasoning_confidence : 0,
    advice_confidence: typeof basis.advice_confidence === 'number' ? basis.advice_confidence : 0,
  }
}

function toStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function confidenceText(value: unknown): string {
  const score = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(score)) return '-'
  const label = score >= 0.85 ? '高' : score >= 0.6 ? '中' : '低'
  return `${label}（${Math.round(score * 100)}%）`
}

function toRecordList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(isRecord) : []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
</script>

<template>
  <div class="report-analysis-page">
    <div class="report-analysis-page__header">
      <div>
        <h1>报告分析</h1>
        <p class="page-subtitle">{{ pageTitle }}</p>
      </div>
    </div>

    <div class="domain-tabs">
      <button
        v-for="tab in domainTabs"
        :key="tab.key"
        :class="['domain-tab', { 'domain-tab--active': queryDomain === tab.key }]"
        @click="selectDomain(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>


    <div class="analyze-bar">
      <div class="analyze-bar__params">
        <span class="param-tag">{{ activeDomain }}</span>
        <span v-if="activeTab !== activeDomain" class="param-tag">{{ activeTab }}</span>
        <span class="param-tag">{{ timeDimensionLabel(queryTimeDim) }}</span>
        <span v-if="queryDate" class="param-tag">{{ queryDate }}</span>
      </div>
      <p class="analyze-bar__hint">
        新报告仅从运营总览首页的「AI 智能分析」入口生成；切换页签或刷新只展示已有报告。
      </p>
    </div>

    <p v-if="pageError" class="page-error">{{ pageError }}</p>

    <div class="report-analysis-workspace">
      <aside class="record-list" aria-label="分析报告列表">
        <div class="record-list__header">
          <strong>分析记录</strong>
          <span v-if="loadingRecords">加载中...</span>
        </div>
        <div v-if="!loadingRecords && !records.length && !isGenerating" class="record-list__empty">暂无分析记录</div>
        <div v-if="isGenerating" class="record-item record-item--generating">
          <span class="record-item__title">
            <span class="generating-dot" />
            正在生成报告...
          </span>
          <span class="record-item__meta">{{ activeDomain }} / {{ displayParams.join(' ') }}</span>
          <span class="record-item__summary">AI 分析进行中，请稍候...</span>
        </div>
        <button
          v-for="record in records"
          :key="record.id"
          type="button"
          class="record-item"
          :class="{ 'record-item--active': selectedRecordId === record.id }"
          @click="selectRecord(record.id)"
        >
          <span class="record-item__title">{{ record.report_name || '运营分析报告' }}</span>
          <span class="record-item__meta">{{ formatRecordMeta(record) }}</span>
          <span class="record-item__time">{{ formatTime(record.created_at) }}</span>
        </button>
      </aside>

      <section class="report-preview">
        <template v-if="progressStore.loading || store.loading || progressStore.status === 'failed'">
          <div class="operation-progress">
            <div class="progress-card">
              <h3>{{ progressStore.status === 'failed' ? '分析失败' : '分析进行中' }} — {{ activeDomain }}</h3>
              <div v-if="progressStore.error" class="progress-error">{{ progressStore.error }}</div>
              <div class="step-list">
                <div
                  v-for="step in progressStore.steps"
                  :key="step.key"
                  class="step-item"
                  :class="{
                    'step-item--past': step.status === 'completed',
                    'step-item--current': step.status === 'running',
                    'step-item--future': step.status === 'pending',
                    'step-item--failed': step.status === 'failed',
                  }"
                >
                  <span class="step-icon">
                    <span v-if="step.status === 'completed'" class="step-dot step-dot--done">✓</span>
                    <span v-else-if="step.status === 'running'" class="step-dot step-dot--active" />
                    <span v-else-if="step.status === 'failed'" class="step-dot step-dot--failed">✗</span>
                    <span v-else class="step-dot step-dot--pending" />
                  </span>
                  <span class="step-label" :class="{ 'step-label--active': step.status === 'running', 'step-label--failed': step.status === 'failed' }">
                    {{ step.title }}
                    <span v-if="step.status === 'completed' && step.durationMs !== null" class="step-duration">{{ step.durationMs }}ms</span>
                    <span v-if="step.status === 'completed' && step.sourceLabel" class="step-source">· {{ step.sourceLabel }}</span>
                    <span v-if="step.status === 'failed' && step.errorMessage" class="step-error-msg">{{ step.errorMessage }}</span>
                  </span>
                </div>
              </div>
              <div v-if="progressStore.streamedReport" class="streaming-report">
                <div class="streaming-report__title">报告内容生成中</div>
                <div
                  class="streaming-report__body markdown-content"
                  v-html="renderMarkdown(progressStore.streamedReport)"
                />
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="loadingDetail">
          <div class="report-preview__empty">正在加载报告...</div>
        </template>

        <template v-else-if="selectedRecord && userSelected">
          <header class="report-preview__header">
            <div>
              <h2>{{ selectedRecord.report_name || '运营分析报告' }}</h2>
              <p>{{ formatRecordMeta(selectedRecord) }} / {{ formatTime(selectedRecord.created_at) }}</p>
            </div>
            <div class="report-preview__header-actions">
              <span class="status-pill">{{ selectedRecord.status }}</span>
              <a :href="getDownloadUrl(selectedRecord.id)" class="btn-download" download>下载报告</a>
            </div>
          </header>
          <div class="report-preview__body markdown-content" v-html="renderMarkdown(selectedRecord.final_answer_markdown || selectedRecord.summary_text || '')" />
        </template>

        <template v-else-if="hasResult">
          <header class="report-preview__header">
            <div>
              <h2>AI 运营分析结论 — {{ activeDomain }}</h2>
              <p v-if="displayParams.length">{{ displayParams.join(' / ') }}</p>
            </div>
            <div class="report-preview__header-actions">
              <span class="status-pill">{{ store.result?.status }}</span>
              <button class="btn-download" :disabled="!canDownload" @click="downloadReport">下载报告</button>
            </div>
          </header>
          <div class="report-preview__body">
            <div class="result-section result-section--summary">
              <div class="markdown-content" v-html="renderMarkdown(store.result!.summary)" />
            </div>
            <div v-if="store.result!.advice_items.length" class="result-section">
              <h3>建议动作</h3>
              <div v-for="(item, i) in store.result!.advice_items" :key="i" class="advice-card">
                <div class="advice-card__header">
                  <span class="advice-priority" :class="`advice-priority--${(item.priority as string || 'P2').toLowerCase()}`">{{ item.priority || 'P2' }}</span>
                  <strong>{{ item.title }}</strong>
                </div>
                <p class="advice-card__action">{{ item.action }}</p>
                <p v-if="item.owner_role" class="advice-card__meta">负责人：{{ item.owner_role }}</p>
                <p v-if="item.expected_result" class="advice-card__meta">预期：{{ item.expected_result }}</p>
                <p v-if="item.confidence !== undefined" class="advice-card__meta">建议置信度：{{ confidenceText(item.confidence) }}</p>
                <p v-if="Array.isArray(item.assumptions) && item.assumptions.length" class="advice-card__boundary">
                  边界：{{ item.assumptions.join('；') }}
                </p>
              </div>
            </div>
            <div v-if="store.result!.evidence.length || store.result!.analysis_basis.knowledge_note" class="result-section">
              <h3>分析依据分层</h3>
              <div class="basis-summary">
                <span class="basis-badge basis-badge--fact">业务事实</span>
                <span>原因分析置信度：{{ confidenceText(store.result!.analysis_basis.reasoning_confidence) }}</span>
                <span>建议置信度：{{ confidenceText(store.result!.analysis_basis.advice_confidence) }}</span>
              </div>
              <h4>业务数据依据</h4>
              <div class="evidence-list">
                <div v-for="(ev, i) in store.result!.evidence" :key="i" class="evidence-item">
                  <span class="evidence-source">{{ ev.source }}</span>
                  <span class="evidence-desc">{{ ev.description }}</span>
                </div>
              </div>
              <h4>知识与制度依据</h4>
              <div v-if="store.result!.analysis_basis.knowledge_evidence.length" class="evidence-list">
                <div v-for="(ev, i) in store.result!.analysis_basis.knowledge_evidence" :key="i" class="evidence-item">
                  <span class="evidence-source">{{ ev.source }}</span>
                  <span class="evidence-desc">{{ ev.description }}</span>
                </div>
              </div>
              <p v-else class="knowledge-note">{{ store.result!.analysis_basis.knowledge_note }}</p>
              <template v-if="store.result!.analysis_basis.assumptions.length">
                <h4>分析假设</h4>
                <ul class="basis-list">
                  <li v-for="(item, i) in store.result!.analysis_basis.assumptions" :key="i">{{ item }}</li>
                </ul>
              </template>
              <template v-if="store.result!.analysis_basis.verification_steps.length">
                <h4>待核查事项</h4>
                <ul class="basis-list">
                  <li v-for="(item, i) in store.result!.analysis_basis.verification_steps" :key="i">{{ item }}</li>
                </ul>
              </template>
            </div>
            <div class="result-meta">
              <span>状态：{{ store.result!.status }}</span>
              <span>Trace：<code>{{ store.result!.trace_id }}</code></span>
            </div>
          </div>
        </template>

        <template v-else-if="selectedRecord">
          <header class="report-preview__header">
            <div>
              <h2>{{ selectedRecord.report_name || '运营分析报告' }}</h2>
              <p>{{ formatRecordMeta(selectedRecord) }} / {{ formatTime(selectedRecord.created_at) }}</p>
            </div>
            <div class="report-preview__header-actions">
              <span class="status-pill">{{ selectedRecord.status }}</span>
              <a :href="getDownloadUrl(selectedRecord.id)" class="btn-download" download>下载报告</a>
            </div>
          </header>
          <div class="report-preview__body markdown-content" v-html="renderMarkdown(selectedRecord.final_answer_markdown || selectedRecord.summary_text || '')" />
        </template>

        <template v-else>
          <div class="report-preview__empty">
            <p>当前筛选条件下暂无报告。请返回运营总览首页，点击「AI 智能分析」生成新报告。</p>
          </div>
        </template>
      </section>

      <ReportChatPanel
        class="report-chat-workspace__panel"
        :report-id="chatReportId"
        :report-title="selectedReportTitle"
      />
    </div>
  </div>
</template>

<style scoped>
.report-analysis-page {
  max-width: 1640px;
}

.report-analysis-page__header {
  align-items: center;
  display: flex;
  gap: 20px;
  justify-content: space-between;
  margin-bottom: 12px;
}

.report-analysis-page__header h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0 0 4px;
}

.page-subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0;
}

.domain-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}

.domain-tab {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  padding: 9px 18px;
}

.domain-tab--active {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #3730a3;
}

.analyze-bar {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.analyze-bar__params {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.analyze-bar__hint {
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.5;
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
  font-size: 14px;
  font-weight: 800;
  justify-content: center;
  min-height: 38px;
  padding: 0 22px;
}

.btn-analyze:disabled {
  cursor: wait;
  opacity: 0.6;
}

.page-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  font-size: 14px;
  margin-bottom: 16px;
  padding: 12px 16px;
}

.report-analysis-workspace {
  align-items: stretch;
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(240px, 300px) minmax(420px, 1fr) minmax(360px, 460px);
}

.record-list,
.report-preview {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.record-list {
  max-height: calc(100vh - 230px);
  min-height: 580px;
  overflow-y: auto;
}

.record-list__header {
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-heading);
  display: flex;
  font-size: 14px;
  justify-content: space-between;
  padding: 14px 16px;
}

.record-list__header span,
.record-list__empty {
  color: var(--color-text-muted);
  font-size: 13px;
}

.record-list__empty {
  padding: 36px 16px;
  text-align: center;
}

.record-item {
  background: transparent;
  border: none;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  display: block;
  padding: 14px 16px;
  text-align: left;
  width: 100%;
}

.record-item:hover,
.record-item--active {
  background: #f8fafc;
}

.record-item--active {
  box-shadow: inset 3px 0 0 #6366f1;
}

.record-item--generating {
  background: #fffbeb;
  border-bottom: 1px solid #fde68a;
  cursor: default;
}

.record-item--generating .record-item__title {
  align-items: center;
  display: flex;
  gap: 10px;
}

.generating-dot {
  animation: pulse 1.5s infinite;
  background: #f59e0b;
  border-radius: 50%;
  display: inline-block;
  height: 10px;
  width: 10px;
}

.record-item__title,
.record-item__meta,
.record-item__summary {
  display: block;
}

.record-item__title {
  color: var(--color-heading);
  font-size: 14px;
  font-weight: 800;
  line-height: 1.4;
  margin-bottom: 6px;
}

.record-item__meta {
  color: #6366f1;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 6px;
}

.record-item__summary {
  color: var(--color-text-muted);
  display: -webkit-box;
  font-size: 13px;
  line-height: 1.5;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.record-item__time {
  color: var(--color-text-muted);
  font-size: 12px;
}

.report-preview {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 230px);
  min-height: 580px;
  overflow: hidden;
}

.report-preview__header {
  align-items: flex-start;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 18px 20px;
}

.report-preview__header h2 {
  color: var(--color-heading);
  font-size: 18px;
  margin: 0 0 6px;
}

.report-preview__header p {
  color: var(--color-text-muted);
  font-size: 13px;
  margin: 0;
}

.report-preview__header-actions {
  align-items: center;
  display: flex;
  flex-shrink: 0;
  gap: 10px;
}

.report-preview__body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.report-preview__empty {
  color: var(--color-text-muted);
  font-size: 14px;
  padding: 80px 20px;
  text-align: center;
}

.report-chat-workspace__panel {
  max-height: calc(100vh - 230px);
  min-height: 580px;
}

.status-pill {
  background: #f0fdf4;
  border-radius: 999px;
  color: #166534;
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 800;
  padding: 4px 10px;
}

.btn-download {
  align-items: center;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: var(--color-heading);
  cursor: pointer;
  display: inline-flex;
  font-size: 13px;
  font-weight: 800;
  justify-content: center;
  min-height: 34px;
  padding: 0 14px;
  text-decoration: none;
  white-space: nowrap;
}

.btn-download:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.operation-progress {
  padding: 20px;
}

.progress-card {
  padding: 16px;
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

.streaming-report {
  border-top: 1px solid var(--color-border);
  margin-top: 16px;
  padding-top: 16px;
}

.streaming-report__title {
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 800;
  margin-bottom: 8px;
}

.streaming-report__body {
  max-height: 360px;
  overflow-y: auto;
}

.step-item {
  align-items: center;
  display: flex;
  gap: 12px;
  min-height: 36px;
  padding: 4px 0;
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

.step-item--failed .step-label {
  color: #dc2626;
}

.step-label--failed {
  color: #dc2626;
  font-weight: 700;
}

.step-dot--failed {
  align-items: center;
  background: #dc2626;
  color: #ffffff;
  display: flex;
  font-size: 11px;
  font-weight: 800;
  height: 20px;
  justify-content: center;
  width: 20px;
}

.step-duration {
  color: #6366f1;
  font-size: 12px;
  font-weight: 700;
  margin-left: 6px;
}

.step-source {
  color: #94a3b8;
  font-size: 11px;
  font-weight: 400;
  margin-left: 2px;
}

.step-error-msg {
  color: #dc2626;
  display: block;
  font-size: 12px;
  font-weight: 400;
  margin-top: 2px;
}

.progress-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #dc2626;
  font-size: 13px;
  margin-bottom: 12px;
  padding: 8px 12px;
}

.markdown-content {
  font-size: 14px;
  line-height: 1.8;
}

.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  color: var(--color-heading);
  margin: 20px 0 10px;
}

.markdown-content :deep(p) {
  margin: 8px 0;
}

.markdown-content :deep(table) {
  border-collapse: collapse;
  font-size: 13px;
  margin: 12px 0;
  width: 100%;
}

.markdown-content :deep(td),
.markdown-content :deep(th) {
  border: 1px solid #e2e8f0;
  padding: 8px 10px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: #f8fafc;
}

.markdown-content :deep(code) {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  padding: 2px 6px;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid #6366f1;
  color: var(--color-text-muted);
  margin: 12px 0;
  padding: 8px 16px;
}

.result-section {
  margin-bottom: 20px;
}

.result-section h3 {
  color: var(--color-heading);
  font-size: 16px;
  margin: 0 0 12px;
}

.advice-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;
  padding: 14px;
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

.advice-card__boundary {
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  color: #854d0e;
  font-size: 12px;
  line-height: 1.6;
  margin: 8px 0 0;
  padding: 6px 10px;
}

.basis-summary {
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  font-size: 13px;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
}

.basis-badge {
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 9px;
}

.basis-badge--fact {
  background: #dcfce7;
  color: #166534;
}

.knowledge-note {
  background: #eff6ff;
  border-left: 3px solid #3b82f6;
  color: #1e40af;
  font-size: 13px;
  line-height: 1.6;
  padding: 8px 12px;
}

.basis-list {
  color: var(--color-text);
  font-size: 13px;
  line-height: 1.7;
  margin: 6px 0 14px;
  padding-left: 20px;
}

.evidence-list {
  display: grid;
  gap: 8px;
}

.evidence-item {
  align-items: flex-start;
  display: flex;
  font-size: 13px;
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
  padding-top: 14px;
}

.result-meta code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  padding: 1px 6px;
}

@media (max-width: 1180px) {
  .report-analysis-workspace {
    grid-template-columns: minmax(220px, 300px) minmax(420px, 1fr);
  }

  .report-chat-workspace__panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .report-analysis-page__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .report-analysis-workspace {
    grid-template-columns: 1fr;
  }

  .record-list,
  .report-preview,
  .report-chat-workspace__panel {
    max-height: none;
    min-height: auto;
  }
}
</style>
