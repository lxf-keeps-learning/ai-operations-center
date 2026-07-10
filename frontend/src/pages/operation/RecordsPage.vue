<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getDownloadUrl, getRecordDetail, listRecords, type AnalysisRecord, type AnalysisRecordDetail } from '@/api/records'
import ReportChatPanel from '@/components/ReportChatPanel.vue'
import { renderSafeMarkdown } from '@/utils/markdown'

const domainTabs = [
  { key: '', label: '全部' },
  { key: 'safety', label: '本质安全' },
  { key: 'maintenance', label: '设备运维' },
  { key: 'business', label: '经营改善' },
  { key: 'capability', label: '能力提升' },
]

const activeDomain = ref('')
const records = ref<AnalysisRecord[]>([])
const loading = ref(false)
const error = ref('')
const selectedRecord = ref<AnalysisRecordDetail | null>(null)
const showDetail = ref(false)

async function fetchRecords() {
  loading.value = true
  error.value = ''
  try {
    records.value = await listRecords({ domain: activeDomain.value || undefined })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function openDetail(id: number) {
  try {
    selectedRecord.value = await getRecordDetail(id)
    showDetail.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载详情失败'
  }
}

function closeDetail() {
  showDetail.value = false
  selectedRecord.value = null
}

function renderMd(text: string | null): string {
  if (!text) return ''
  return renderSafeMarkdown(text)
}

const domainLabel: Record<string, string> = {
  safety: '本质安全', maintenance: '设备运维', business: '经营改善', capability: '能力提升',
}

const timeDimensionLabel: Record<string, string> = {
  day: '日报', week: '周报', month: '月报',
}

function formatFilter(r: AnalysisRecord): string {
  const parts: string[] = []
  if (r.time_dimension) {
    parts.push(timeDimensionLabel[r.time_dimension] || r.time_dimension)
  }
  if (r.analysis_date) {
    parts.push(r.analysis_date)
  } else if (r.time_dimension === 'month' && r.created_at) {
    parts.push(r.created_at.slice(0, 7))
  } else if (r.time_dimension === 'day' && r.created_at) {
    parts.push(r.created_at.slice(0, 10))
  } else if (r.time_dimension === 'week' && r.created_at) {
    parts.push(r.created_at.slice(0, 10))
  }
  return parts.join(' ') || '-'
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return iso.slice(0, 16).replace('T', ' ')
}

onMounted(fetchRecords)
</script>

<template>
  <div class="records-page">
    <div class="records-page__header">
      <h1>分析记录</h1>
      <p class="page-subtitle">运营分析历史记录</p>
    </div>

    <div class="domain-tabs">
      <button
        v-for="tab in domainTabs"
        :key="tab.key"
        :class="['domain-tab', { 'domain-tab--active': activeDomain === tab.key }]"
        @click="activeDomain = tab.key; fetchRecords()"
      >
        {{ tab.label }}
      </button>
    </div>

    <p v-if="error" class="page-error">{{ error }}</p>
    <p v-if="loading" class="page-loading">加载中...</p>

    <div v-if="!loading && !records.length" class="empty-state">暂无分析记录</div>

    <div v-else class="records-table-wrapper">
      <table class="records-table">
        <thead>
          <tr>
            <th>报告名称</th>
            <th>领域</th>
            <th>筛选条件</th>
            <th>摘要</th>
            <th>生成时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td class="cell-name">{{ r.report_name || '运营分析报告' }}</td>
            <td>
              <span class="record-domain" :class="`record-domain--${r.domain}`">{{ domainLabel[r.domain] || r.domain }}</span>
            </td>
            <td class="cell-filter">{{ formatFilter(r) }}</td>
            <td class="cell-summary">{{ r.summary_text || '-' }}</td>
            <td class="cell-time">{{ formatTime(r.created_at) }}</td>
            <td class="cell-actions">
              <button class="btn-text" @click="openDetail(r.id)">详情</button>
              <RouterLink class="btn-text" :to="{ path: '/operation/report-chat', query: { record_id: r.id } }">AI 追问</RouterLink>
              <a :href="getDownloadUrl(r.id)" class="btn-text" download>下载</a>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div v-if="showDetail && selectedRecord" class="detail-overlay" @click.self="closeDetail">
        <div class="detail-modal">
          <div class="detail-modal__header">
            <h2>{{ selectedRecord.report_name || '运营分析报告' }}</h2>
            <button class="btn-close" @click="closeDetail">✕</button>
          </div>
          <div class="detail-modal__meta">
            <span>Domain: {{ domainLabel[selectedRecord.domain] || selectedRecord.domain }}</span>
            <span>Status: {{ selectedRecord.status }}</span>
            <span>Tokens: {{ selectedRecord.total_tokens }}</span>
            <span>Model: {{ selectedRecord.model_name || '-' }}</span>
            <span>时间: {{ formatTime(selectedRecord.created_at) }}</span>
            <span>Trace: <code>{{ selectedRecord.trace_id }}</code></span>
          </div>
          <div class="detail-modal__body detail-modal__body--with-chat">
            <div class="detail-report">
              <div class="markdown-content" v-html="renderMd(selectedRecord.final_answer_markdown)" />
            </div>
            <ReportChatPanel
              class="detail-chat"
              :report-id="selectedRecord.id"
              :report-title="selectedRecord.report_name || '运营分析报告'"
              compact
            />
          </div>
          <div class="detail-modal__footer">
            <a :href="getDownloadUrl(selectedRecord.id)" class="btn-download" download>下载 Markdown 报告</a>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.records-page {
  max-width: 1200px;
}

.records-page__header h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0 0 4px;
}

.page-subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0 0 24px;
}

.domain-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
}

.domain-tab {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px 8px 0 0;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  padding: 10px 20px;
}

.domain-tab--active {
  background: #ffffff;
  border-bottom-color: #ffffff;
  color: var(--color-heading);
}

.page-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  font-size: 14px;
  margin-bottom: 20px;
  padding: 12px 16px;
}

.page-loading {
  color: var(--color-text-muted);
  font-size: 15px;
  padding: 40px 0;
  text-align: center;
}

.empty-state {
  color: var(--color-text-muted);
  font-size: 15px;
  padding: 60px 0;
  text-align: center;
}

.records-table-wrapper {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow-x: auto;
}

.records-table {
  border-collapse: collapse;
  width: 100%;
}

.records-table th {
  background: #f8fafc;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 800;
  padding: 12px 16px;
  text-align: left;
  white-space: nowrap;
}

.records-table td {
  border-bottom: 1px solid #f1f5f9;
  font-size: 14px;
  padding: 12px 16px;
}

.records-table tr:last-child td {
  border-bottom: none;
}

.records-table tr:hover td {
  background: #f8fafc;
}

.cell-name {
  color: var(--color-heading);
  font-weight: 700;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-filter {
  white-space: nowrap;
}

.cell-summary {
  color: var(--color-text-muted);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-time {
  color: var(--color-text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.cell-actions {
  white-space: nowrap;
}

.cell-actions .btn-text + .btn-text {
  margin-left: 12px;
}

.record-domain {
  border-radius: 4px;
  font-size: 12px;
  font-weight: 800;
  padding: 2px 8px;
  white-space: nowrap;
}

.record-domain--safety { background: #fef2f2; color: #991b1b; }
.record-domain--maintenance { background: #fffbeb; color: #854d0e; }
.record-domain--business { background: #f0fdf4; color: #166534; }
.record-domain--capability { background: #eff6ff; color: #1e40af; }

.btn-text {
  background: none;
  border: none;
  color: #6366f1;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  padding: 0;
  text-decoration: none;
}

.detail-overlay {
  align-items: center;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  inset: 0;
  justify-content: center;
  position: fixed;
  z-index: 100;
}

.detail-modal {
  background: #ffffff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  max-width: 1280px;
  width: 90%;
}

.detail-modal__header {
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  justify-content: space-between;
  padding: 20px 24px;
}

.detail-modal__header h2 {
  color: var(--color-heading);
  font-size: 20px;
  margin: 0;
}

.btn-close {
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 20px;
  padding: 4px 8px;
}

.detail-modal__meta {
  border-bottom: 1px solid #e2e8f0;
  color: var(--color-text-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 13px;
  gap: 16px;
  padding: 12px 24px;
}

.detail-modal__meta code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  padding: 1px 6px;
}

.detail-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.detail-modal__body--with-chat {
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 430px);
  min-height: 0;
}

.detail-report {
  min-width: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.detail-chat {
  min-height: 620px;
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

.markdown-content code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  padding: 2px 6px;
}

.detail-modal__footer {
  border-top: 1px solid var(--color-border);
  padding: 16px 24px;
}

.btn-download {
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
  min-height: 40px;
  padding: 0 24px;
  text-decoration: none;
}

@media (max-width: 980px) {
  .detail-modal {
    width: 94%;
  }

  .detail-modal__body--with-chat {
    grid-template-columns: 1fr;
  }

  .detail-chat {
    min-height: 520px;
  }
}
</style>
