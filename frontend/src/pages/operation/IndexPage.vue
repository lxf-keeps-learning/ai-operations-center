<script setup lang="ts">
import { ref } from 'vue'

import { analyzeOperation, type OperationResult } from '@/api/operation'

const loading = ref(false)
const result = ref<OperationResult | null>(null)
const error = ref('')

async function handleAnalyze() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await analyzeOperation({
      trigger_type: 'tab_analysis',
      domain: 'safety',
      active_tab: '本质安全',
      time_dimension: 'month',
      date: '2026-07',
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '分析请求失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="operation-page">
    <div class="operation-page__header">
      <h1>运营分析</h1>
      <p class="page-subtitle">本质安全 — AI 运营分析诊断</p>
    </div>

    <div class="operation-page__actions">
      <button class="btn-analyze" :disabled="loading" @click="handleAnalyze">
        {{ loading ? '分析中...' : '分析' }}
      </button>
    </div>

    <p v-if="error" class="operation-error">{{ error }}</p>

    <div v-if="loading" class="operation-loading">
      <p>正在分析运营数据，请稍候...</p>
    </div>

    <div v-if="result" class="operation-result">
      <div class="result-section result-section--summary">
        <h2>AI 运营分析结论</h2>
        <div class="markdown-content">{{ result.summary }}</div>
      </div>

      <div v-if="result.advice_items.length" class="result-section">
        <h2>建议动作</h2>
        <div v-for="(item, i) in result.advice_items" :key="i" class="advice-card">
          <div class="advice-card__header">
            <span class="advice-priority" :class="`advice-priority--${(item.priority as string || 'P2').toLowerCase()}`">
              {{ item.priority || 'P2' }}
            </span>
            <strong>{{ item.title }}</strong>
          </div>
          <p class="advice-card__action">{{ item.action }}</p>
          <p class="advice-card__meta" v-if="item.owner_role">负责人：{{ item.owner_role }}</p>
          <p class="advice-card__meta" v-if="item.expected_result">预期：{{ item.expected_result }}</p>
        </div>
      </div>

      <div v-if="result.evidence.length" class="result-section">
        <h2>数据依据</h2>
        <div class="evidence-list">
          <div v-for="(ev, i) in result.evidence" :key="i" class="evidence-item">
            <span class="evidence-source">{{ ev.source }}</span>
            <span class="evidence-desc">{{ ev.description }}</span>
          </div>
        </div>
      </div>

      <div class="result-meta">
        <span>状态：{{ result.status }}</span>
        <span>Trace：<code>{{ result.trace_id }}</code></span>
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
  margin-bottom: 20px;
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

.btn-analyze:disabled {
  cursor: wait;
  opacity: 0.6;
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

.operation-loading {
  color: var(--color-text-muted);
  font-size: 15px;
  padding: 40px 0;
  text-align: center;
}

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
  white-space: pre-wrap;
}

.markdown-content :deep(h3) {
  color: var(--color-heading);
  font-size: 16px;
  margin: 20px 0 10px;
}

.markdown-content :deep(table) {
  border-collapse: collapse;
  font-size: 14px;
  margin: 12px 0;
  width: 100%;
}

.markdown-content :deep(td),
.markdown-content :deep(th) {
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: #f8fafc;
  font-weight: 800;
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
