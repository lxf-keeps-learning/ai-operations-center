<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getRecordDetail, listRecords, type AnalysisRecord, type AnalysisRecordDetail } from '@/api/records'
import ReportChatPanel from '@/components/ReportChatPanel.vue'
import { renderSafeMarkdown } from '@/utils/markdown'

const domainTabs = [
  { key: '', label: '全部' },
  { key: 'safety', label: '本质安全' },
  { key: 'maintenance', label: '设备运维' },
  { key: 'business', label: '经营改善' },
  { key: 'capability', label: '能力提升' },
]

const route = useRoute()
const router = useRouter()

const activeDomain = ref('')
const records = ref<AnalysisRecord[]>([])
const selectedRecord = ref<AnalysisRecordDetail | null>(null)
const loadingRecords = ref(false)
const loadingDetail = ref(false)
const error = ref('')

const selectedRecordId = computed(() => selectedRecord.value?.id ?? null)
const selectedReportTitle = computed(() => selectedRecord.value?.report_name || '运营分析报告')

const domainLabel: Record<string, string> = {
  safety: '本质安全',
  maintenance: '设备运维',
  business: '经营改善',
  capability: '能力提升',
}

const timeDimensionLabel: Record<string, string> = {
  day: '日报',
  week: '周报',
  month: '月报',
  quarter: '季报',
  year: '年报',
}

watch(
  () => route.query.record_id,
  (value) => {
    const id = normalizeQueryId(value)
    if (id && id !== selectedRecord.value?.id) {
      void selectRecord(id, false)
    }
  },
)

async function fetchRecords() {
  loadingRecords.value = true
  error.value = ''
  try {
    records.value = await listRecords({
      domain: activeDomain.value || undefined,
      page_size: 50,
    })
    const routeId = normalizeQueryId(route.query.record_id)
    const fallbackId = records.value[0]?.id
    const nextId = routeId || fallbackId
    if (nextId) {
      await selectRecord(nextId, false)
    } else {
      selectedRecord.value = null
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载分析记录失败'
  } finally {
    loadingRecords.value = false
  }
}

async function selectRecord(id: number, syncRoute = true) {
  loadingDetail.value = true
  error.value = ''
  try {
    selectedRecord.value = await getRecordDetail(id)
    if (syncRoute) {
      await router.replace({
        path: '/operation/report-chat',
        query: { ...route.query, record_id: String(id) },
      })
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载报告详情失败'
  } finally {
    loadingDetail.value = false
  }
}

function switchDomain(domain: string) {
  activeDomain.value = domain
  void router.replace({ path: '/operation/report-chat' })
  void fetchRecords()
}

function renderMd(text: string | null): string {
  if (!text) return ''
  return renderSafeMarkdown(text)
}

function normalizeQueryId(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const id = Number(raw)
  return Number.isInteger(id) && id > 0 ? id : null
}

function formatRecordMeta(record: AnalysisRecord): string {
  const parts = [
    domainLabel[record.domain] || record.domain,
    record.time_dimension ? timeDimensionLabel[record.time_dimension] || record.time_dimension : '',
    record.analysis_date || formatDate(record.created_at),
  ].filter(Boolean)
  return parts.join(' / ')
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return iso.slice(0, 16).replace('T', ' ')
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return iso.slice(0, 10)
}

onMounted(fetchRecords)
</script>

<template>
  <div class="report-chat-page">
    <div class="report-chat-page__header">
      <div>
        <h1>报告追问</h1>
        <p class="page-subtitle">围绕已生成的本质安全/运营分析报告继续下钻原因、风险排序和建议动作。</p>
      </div>
      <RouterLink class="btn-secondary" to="/operation/records">查看分析记录</RouterLink>
    </div>

    <div class="domain-tabs">
      <button
        v-for="tab in domainTabs"
        :key="tab.key"
        :class="['domain-tab', { 'domain-tab--active': activeDomain === tab.key }]"
        @click="switchDomain(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <p v-if="error" class="page-error">{{ error }}</p>

    <div class="report-chat-workspace">
      <aside class="record-list" aria-label="分析报告列表">
        <div class="record-list__header">
          <strong>选择报告</strong>
          <span v-if="loadingRecords">加载中...</span>
        </div>
        <div v-if="!loadingRecords && !records.length" class="record-list__empty">暂无分析记录</div>
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
          <span class="record-item__summary">{{ record.summary_text || '暂无摘要' }}</span>
        </button>
      </aside>

      <section class="report-preview">
        <div v-if="loadingDetail" class="report-preview__empty">正在加载报告...</div>
        <template v-else-if="selectedRecord">
          <header class="report-preview__header">
            <div>
              <h2>{{ selectedRecord.report_name || '运营分析报告' }}</h2>
              <p>{{ formatRecordMeta(selectedRecord) }} / {{ formatTime(selectedRecord.created_at) }}</p>
            </div>
            <span class="status-pill">{{ selectedRecord.status }}</span>
          </header>
          <div class="report-preview__body markdown-content" v-html="renderMd(selectedRecord.final_answer_markdown || selectedRecord.summary_text)" />
        </template>
        <div v-else class="report-preview__empty">请选择一份报告查看内容。</div>
      </section>

      <ReportChatPanel
        class="report-chat-workspace__panel"
        :report-id="selectedRecordId"
        :report-title="selectedReportTitle"
      />
    </div>
  </div>
</template>

<style scoped>
.report-chat-page {
  max-width: 1640px;
}

.report-chat-page__header {
  align-items: center;
  display: flex;
  gap: 20px;
  justify-content: space-between;
  margin-bottom: 20px;
}

.report-chat-page__header h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0 0 4px;
}

.page-subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0;
}

.btn-secondary {
  align-items: center;
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: #3730a3;
  display: inline-flex;
  font-size: 14px;
  font-weight: 800;
  min-height: 40px;
  padding: 0 16px;
  text-decoration: none;
  white-space: nowrap;
}

.domain-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 16px;
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

.page-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  font-size: 14px;
  margin-bottom: 16px;
  padding: 12px 16px;
}

.report-chat-workspace {
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
  max-height: calc(100vh - 190px);
  min-height: 620px;
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

.report-preview {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 190px);
  min-height: 620px;
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
  font-size: 20px;
  margin: 0 0 6px;
}

.report-preview__header p {
  color: var(--color-text-muted);
  font-size: 13px;
  margin: 0;
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

.report-preview__body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.report-preview__empty {
  color: var(--color-text-muted);
  font-size: 14px;
  padding: 60px 20px;
  text-align: center;
}

.report-chat-workspace__panel {
  max-height: calc(100vh - 190px);
  min-height: 620px;
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

@media (max-width: 1180px) {
  .report-chat-workspace {
    grid-template-columns: minmax(220px, 300px) minmax(420px, 1fr);
  }

  .report-chat-workspace__panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .report-chat-page__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .report-chat-workspace {
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
