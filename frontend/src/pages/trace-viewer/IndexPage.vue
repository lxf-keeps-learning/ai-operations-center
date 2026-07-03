<script setup lang="ts">
import { ref } from 'vue'

import { getTrace } from '@/api/trace'
import type { TraceData } from '@/api/trace'
import StatusCard from '@/components/status-card/StatusCard.vue'

const traceId = ref('')
const traceData = ref<TraceData | null>(null)
const loading = ref(false)
const error = ref('')

async function handleQuery() {
  const tid = traceId.value.trim()
  if (!tid) return
  loading.value = true
  error.value = ''
  traceData.value = null
  try {
    traceData.value = await getTrace(tid)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '查询失败'
  } finally {
    loading.value = false
  }
}

function spanStatusClass(status: string) {
  if (status === 'OK') return 'status-ok'
  if (status === 'ERROR') return 'status-error'
  return 'status-unknown'
}
</script>

<template>
  <div class="trace-viewer">
    <h1>Trace 查询</h1>
    <p class="page-subtitle">输入 traceId 查询全链路追踪信息（Sprint1 mock 数据）</p>

    <form class="trace-form" @submit.prevent="handleQuery">
      <input
        v-model="traceId"
        class="trace-form__input"
        placeholder="输入 traceId，例如 trace_20260703_xxx"
      />
      <button class="trace-form__btn" type="submit" :disabled="loading || !traceId.trim()">
        {{ loading ? '查询中...' : '查询' }}
      </button>
    </form>

    <p v-if="error" class="page-error">{{ error }}</p>

    <section v-if="traceData" class="trace-result">
      <div class="trace-info">
        <StatusCard label="Trace ID" :value="traceData.traceId" tone="info" />
        <StatusCard label="Span 数量" :value="traceData.spans.length" tone="info" />
      </div>

      <div class="timeline">
        <div v-for="span in traceData.spans" :key="span.spanId" class="timeline__item">
          <div class="timeline__dot" :class="spanStatusClass(span.status)" />
          <div class="timeline__content">
            <div class="timeline__header">
              <strong>{{ span.operation }}</strong>
              <span class="timeline__service">{{ span.service }}</span>
              <span class="timeline__status" :class="spanStatusClass(span.status)">{{ span.status }}</span>
            </div>
            <div class="timeline__meta">
              <span>spanId: <code>{{ span.spanId }}</code></span>
              <span>{{ span.startTime }} → {{ span.endTime }}</span>
            </div>
            <div v-if="span.metadata" class="timeline__metadata">
              <pre>{{ JSON.stringify(span.metadata, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0 0 4px;
}

.page-subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0 0 24px;
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

.trace-form {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.trace-form__input {
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  flex: 1;
  font-family: ui-monospace, monospace;
  font-size: 14px;
  min-width: 0;
  padding: 10px 14px;
}

.trace-form__input:focus {
  border-color: #6366f1;
  outline: none;
}

.trace-form__btn {
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
  padding: 0 24px;
  white-space: nowrap;
}

.trace-form__btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.trace-info {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  margin-bottom: 24px;
}

.timeline {
  position: relative;
}

.timeline::before {
  background: #e2e8f0;
  bottom: 0;
  content: '';
  left: 15px;
  position: absolute;
  top: 0;
  width: 2px;
}

.timeline__item {
  align-items: flex-start;
  display: flex;
  gap: 20px;
  padding-bottom: 20px;
  position: relative;
}

.timeline__dot {
  background: #ffffff;
  border: 3px solid #94a3b8;
  border-radius: 50%;
  flex-shrink: 0;
  height: 14px;
  margin-top: 4px;
  width: 14px;
  z-index: 1;
}

.timeline__dot.status-ok    { border-color: #16a34a; }
.timeline__dot.status-error { border-color: #dc2626; }

.timeline__content {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  flex: 1;
  padding: 16px;
}

.timeline__header {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 6px;
}

.timeline__header strong {
  color: var(--color-heading);
  font-size: 16px;
}

.timeline__service {
  background: #f1f5f9;
  border-radius: 4px;
  color: var(--color-text-muted);
  font-family: ui-monospace, monospace;
  font-size: 12px;
  padding: 2px 8px;
}

.timeline__status {
  border-radius: 4px;
  font-size: 11px;
  font-weight: 800;
  padding: 2px 8px;
  text-transform: uppercase;
}

.timeline__status.status-ok    { background: #f0fdf4; color: #166534; }
.timeline__status.status-error { background: #fef2f2; color: #991b1b; }

.timeline__meta {
  color: var(--color-text-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 13px;
  gap: 16px;
}

.timeline__meta code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  padding: 1px 6px;
}

.timeline__metadata {
  margin-top: 8px;
}

.timeline__metadata pre {
  background: #101828;
  border-radius: 6px;
  color: #e0f2fe;
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
  overflow-x: auto;
  padding: 12px;
}
</style>
