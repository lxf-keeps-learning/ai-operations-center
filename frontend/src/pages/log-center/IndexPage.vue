<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getLlmUsageLogs, getRecentLogs } from '@/api/logs'
import DataTable from '@/components/data-table/DataTable.vue'
import type { LogEntry, LlmUsageLog } from '@/types/log'

type Tab = 'api' | 'operation' | 'llm' | 'exception'
const activeTab = ref<Tab>('api')
const logs = ref<LogEntry[]>([])
const llmLogs = ref<LlmUsageLog[]>([])
const loading = ref(true)
const error = ref('')

const mockOperationLogs = [
  { time: '2026-07-03T09:50:00', user: 'admin', action: '切换默认模型', target: 'qwen → deepseek', traceId: 'trace_op_001' },
  { time: '2026-07-03T09:45:00', user: 'admin', action: '修改配置', target: 'max_output_tokens: 2000', traceId: 'trace_op_002' },
  { time: '2026-07-03T09:30:00', user: 'operator', action: '查看日志', target: 'LLM 调用日志', traceId: 'trace_op_003' },
]

const mockExceptionLogs = [
  { time: '2026-07-03T10:03:00', code: 500101, message: 'LLM 调用超时', traceId: 'trace_20260703_ddd', service: 'llm' },
  { time: '2026-07-03T10:01:00', code: 404001, message: 'Item 不存在', traceId: 'trace_20260703_bbb', service: 'api' },
  { time: '2026-07-03T09:55:00', code: 500001, message: '数据库连接超时', traceId: 'trace_err_001', service: 'db' },
]

const logColumns = [
  { key: 'time', label: '时间', width: '160px' },
  { key: 'level', label: '级别', width: '80px' },
  { key: 'method', label: '方法', width: '60px' },
  { key: 'path', label: '路径' },
  { key: 'status', label: '状态码', width: '80px' },
  { key: 'durationMs', label: '耗时', width: '80px' },
  { key: 'traceId', label: 'TraceId', width: '240px' },
]

const operationColumns = [
  { key: 'time', label: '时间', width: '160px' },
  { key: 'user', label: '用户', width: '100px' },
  { key: 'action', label: '操作', width: '140px' },
  { key: 'target', label: '操作对象' },
  { key: 'traceId', label: 'TraceId', width: '240px' },
]

const llmColumns = [
  { key: 'provider', label: '供应商', width: '100px' },
  { key: 'model', label: '模型', width: '140px' },
  { key: 'inputTokens', label: '输入 tokens', width: '100px' },
  { key: 'outputTokens', label: '输出 tokens', width: '100px' },
  { key: 'totalTokens', label: '总 tokens', width: '100px' },
  { key: 'durationMs', label: '耗时', width: '80px' },
  { key: 'success', label: '成功', width: '60px' },
  { key: 'traceId', label: 'TraceId', width: '240px' },
]

const exceptionColumns = [
  { key: 'time', label: '时间', width: '160px' },
  { key: 'code', label: '错误码', width: '80px' },
  { key: 'message', label: '错误信息' },
  { key: 'service', label: '来源', width: '80px' },
  { key: 'traceId', label: 'TraceId', width: '240px' },
]

const levelClass = (level: string) => {
  if (level === 'ERROR') return 'tag tag--danger'
  if (level === 'WARNING') return 'tag tag--warning'
  return 'tag tag--info'
}

onMounted(async () => {
  try {
    const [l, ll] = await Promise.all([getRecentLogs(), getLlmUsageLogs()])
    logs.value = l
    llmLogs.value = ll
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="log-center">
    <h1>日志中心</h1>
    <p class="page-subtitle">Sprint1 mock 数据 — 展示四种日志类型</p>

    <div v-if="loading" class="page-loading">加载中...</div>
    <p v-else-if="error" class="page-error">{{ error }}</p>

    <template v-else>
      <div class="tabs">
        <button :class="['tab', { 'tab--active': activeTab === 'api' }]" @click="activeTab = 'api'">
          API 日志 ({{ logs.length }})
        </button>
        <button :class="['tab', { 'tab--active': activeTab === 'operation' }]" @click="activeTab = 'operation'">
          操作日志 ({{ mockOperationLogs.length }})
        </button>
        <button :class="['tab', { 'tab--active': activeTab === 'llm' }]" @click="activeTab = 'llm'">
          LLM 调用日志 ({{ llmLogs.length }})
        </button>
        <button :class="['tab', { 'tab--active': activeTab === 'exception' }]" @click="activeTab = 'exception'">
          异常日志 ({{ mockExceptionLogs.length }})
        </button>
      </div>

      <section v-if="activeTab === 'api'">
        <DataTable :columns="logColumns" :rows="logs as unknown as Record<string, unknown>[]">
          <template #cell-level="{ value }">
            <span :class="levelClass(value as string)">{{ value }}</span>
          </template>
          <template #cell-status="{ value }">
            <span :class="(value as number) >= 400 ? 'tag tag--danger' : 'tag tag--info'">{{ value }}</span>
          </template>
        </DataTable>
      </section>

      <section v-if="activeTab === 'operation'">
        <DataTable :columns="operationColumns" :rows="mockOperationLogs as unknown as Record<string, unknown>[]" />
      </section>

      <section v-if="activeTab === 'llm'">
        <DataTable :columns="llmColumns" :rows="llmLogs as unknown as Record<string, unknown>[]">
          <template #cell-success="{ value }">
            <span :class="value ? 'tag tag--success' : 'tag tag--danger'">{{ value ? '是' : '否' }}</span>
          </template>
        </DataTable>
      </section>

      <section v-if="activeTab === 'exception'">
        <DataTable :columns="exceptionColumns" :rows="mockExceptionLogs as unknown as Record<string, unknown>[]">
          <template #cell-code="{ value }">
            <code>{{ value }}</code>
          </template>
        </DataTable>
      </section>
    </template>
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

.page-loading,
.page-error {
  font-size: 15px;
  margin-bottom: 20px;
}

.page-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  padding: 12px 16px;
}

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
}

.tab {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px 8px 0 0;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  padding: 10px 20px;
}

.tab--active {
  background: #ffffff;
  border-bottom-color: #ffffff;
  color: var(--color-heading);
}

.tag {
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
}

.tag--success { background: #f0fdf4; color: #166534; }
.tag--info    { background: #eff6ff; color: #1e40af; }
.tag--warning { background: #fffbeb; color: #854d0e; }
.tag--danger  { background: #fef2f2; color: #991b1b; }
</style>
