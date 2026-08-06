<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getRuntimeTrace, listRuntimeTraces, type RuntimeTraceSpan } from '@/api/runtime'

const spans = ref<RuntimeTraceSpan[]>([])
const selectedTrace = ref<RuntimeTraceSpan[] | null>(null)
const loading = ref(false)
const error = ref('')
const route = useRoute()

function queryValue(key: string) {
  const value = route.query[key]
  return typeof value === 'string' ? value : ''
}

const traceFilter = ref(queryValue('trace_id'))
const sessionFilter = ref(queryValue('session_id'))
const graphFilter = ref(queryValue('graph_name'))
const spanTypeFilter = ref(queryValue('span_type'))
const pageSize = ref(Number(queryValue('page_size')) || 100)

const traceRows = computed(() => {
  const grouped = new Map<string, RuntimeTraceSpan[]>()
  spans.value.forEach((span) => grouped.set(span.trace_id, [...(grouped.get(span.trace_id) || []), span]))
  return [...grouped.entries()].map(([traceId, items]) => ({ traceId, spans: items, latest: items[items.length - 1] }))
})

function formatTime(value: string | null) { return value ? value.slice(0, 19).replace('T', ' ') : '-' }
function label(span: RuntimeTraceSpan) { return span.node_name || span.tool_name || span.model_name || span.span_type }

async function loadTraces() {
  loading.value = true; error.value = ''
  try {
    spans.value = await listRuntimeTraces({
      session_id: sessionFilter.value || undefined,
      trace_id: traceFilter.value || undefined,
      graph_name: graphFilter.value || undefined,
      span_type: spanTypeFilter.value || undefined,
      page_size: pageSize.value,
    })
  }
  catch (err) { error.value = err instanceof Error ? err.message : 'Trace 列表加载失败' }
  finally { loading.value = false }
}

async function openTrace(traceId: string) {
  try { selectedTrace.value = await getRuntimeTrace(traceId) }
  catch (err) { error.value = err instanceof Error ? err.message : 'Trace 详情加载失败' }
}

onMounted(loadTraces)

function resetFilters() {
  traceFilter.value = ''
  sessionFilter.value = ''
  graphFilter.value = ''
  spanTypeFilter.value = ''
  pageSize.value = 100
  void loadTraces()
}
</script>

<template>
  <div class="trace-page">
    <div class="trace-page__header"><div><h1>Trace 链路记录</h1><p>按一次请求聚合完整 Span，查看 Graph、节点、Prompt、模型和工具调用。</p></div><button class="refresh-btn" type="button" @click="loadTraces">刷新</button></div>
    <form class="trace-toolbar" @submit.prevent="loadTraces"><input v-model="traceFilter" placeholder="按 Trace ID 筛选" /><input v-model="sessionFilter" placeholder="Session ID" /><input v-model="graphFilter" placeholder="Graph 名称" /><input v-model="spanTypeFilter" placeholder="Span 类型" /><select v-model.number="pageSize" aria-label="每页数量"><option :value="50">50 条</option><option :value="100">100 条</option><option :value="200">200 条</option></select><button class="filter-btn" type="submit">筛选</button><button class="filter-btn" type="button" @click="resetFilters">重置</button><span>{{ traceRows.length }} 条链路</span></form>
    <div v-if="error" class="runtime-error">{{ error }}</div>
    <div v-if="loading" class="runtime-empty">加载中...</div>
    <div v-else-if="!traceRows.length" class="runtime-empty">暂无 Trace 链路记录</div>
    <div v-else class="trace-list">
      <article v-for="row in traceRows" :key="row.traceId" class="trace-row" @click="openTrace(row.traceId)">
        <div class="trace-row__main"><code>{{ row.traceId }}</code><strong>{{ row.latest.graph_name || 'Runtime Trace' }}</strong><span>{{ formatTime(row.latest.created_at) }}</span></div>
        <div class="trace-row__meta"><span>{{ row.spans.length }} spans</span><span>{{ row.latest.session_id }}</span><span :class="`trace-status trace-status--${row.latest.status}`">{{ row.latest.status }}</span></div>
        <div class="trace-row__nodes"><span v-for="span in row.spans.slice(0, 6)" :key="span.id">{{ label(span) }}</span></div>
      </article>
    </div>

    <div v-if="selectedTrace" class="runtime-drawer" @click.self="selectedTrace = null"><section class="runtime-drawer__panel"><div class="runtime-drawer__header"><h2>完整 Trace 链路</h2><button type="button" @click="selectedTrace = null">×</button></div><div class="trace-detail__summary"><code>{{ selectedTrace[0]?.trace_id }}</code><span>{{ selectedTrace.length }} spans</span></div><div class="trace-timeline"><article v-for="span in selectedTrace" :key="span.id" class="trace-span"><i :class="`trace-span__dot trace-span__dot--${span.status}`" /><div><h3>{{ label(span) }} <small>{{ span.span_type }}</small></h3><p>{{ span.graph_name || '-' }} / {{ span.model_name || 'non-LLM' }} / {{ formatTime(span.created_at) }}</p><div class="trace-span__facts"><span>耗时 {{ span.cost_ms ?? '-' }} ms</span><span>Token {{ span.total_tokens ?? '-' }}</span><span>状态 {{ span.status }}</span></div><details><summary>查看输入/输出</summary><pre>{{ JSON.stringify({ input: span.input_data, output: span.output_data, prompt: { code: span.prompt_code, version: span.prompt_version }, error: span.error_message }, null, 2) }}</pre></details></div></article></div></section></div>
  </div>
</template>

<style scoped>
.trace-page { max-width: 1500px; }.trace-page__header { align-items: center; display: flex; justify-content: space-between; margin-bottom: 22px; } h1 { color: #14213d; font-size: 28px; margin: 0 0 6px; }.trace-page__header p { color: #71809b; margin: 0; }.refresh-btn { background: #172554; border: 0; border-radius: 8px; color: #fff; cursor: pointer; font-weight: 700; padding: 10px 18px; }
.trace-toolbar { align-items: center; display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }.trace-toolbar input, .trace-toolbar select { border: 1px solid #d7dfeb; border-radius: 8px; min-height: 38px; padding: 0 10px; }.trace-toolbar input { width: 180px; }.trace-toolbar span { color: #71809b; font-size: 13px; }.filter-btn { background: #eef2ff; border: 0; border-radius: 7px; color: #4338ca; cursor: pointer; font: inherit; font-size: 12px; font-weight: 700; min-height: 36px; padding: 0 10px; }.trace-list { display: grid; gap: 12px; }.trace-row { background: #fff; border: 1px solid #dfe6f1; border-radius: 12px; cursor: pointer; padding: 18px 20px; }.trace-row:hover { border-color: #818cf8; box-shadow: 0 8px 24px rgba(79,70,229,.08); }.trace-row__main, .trace-row__meta { align-items: center; display: flex; gap: 18px; }.trace-row__main code { color: #4f46e5; }.trace-row__main strong { color: #263452; }.trace-row__main span, .trace-row__meta { color: #71809b; font-size: 12px; }.trace-row__meta { margin-top: 10px; }.trace-status { color: #166534; }.trace-status--error, .trace-status--failed { color: #b91c1c; }.trace-row__nodes { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 13px; }.trace-row__nodes span { background: #eef2ff; border-radius: 5px; color: #4f46e5; font-size: 11px; padding: 4px 8px; }
.runtime-error { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #b91c1c; margin-bottom: 16px; padding: 12px 16px; }.runtime-empty { color: #71809b; padding: 64px 20px; text-align: center; }.runtime-drawer { background: rgba(15,23,42,.42); inset: 0; position: fixed; z-index: 20; }.runtime-drawer__panel { background: #fff; height: 100%; max-width: 760px; overflow: auto; padding: 28px; position: absolute; right: 0; width: 64%; }.runtime-drawer__header { align-items: center; display: flex; justify-content: space-between; }.runtime-drawer__header h2 { color: #14213d; margin: 0; }.runtime-drawer__header button { background: none; border: 0; color: #64748b; cursor: pointer; font-size: 28px; }.trace-detail__summary { display: flex; gap: 18px; margin: 24px 0; }.trace-detail__summary code { color: #4f46e5; }.trace-detail__summary span { color: #71809b; }.trace-timeline { border-left: 2px solid #e2e8f0; margin-left: 7px; padding-left: 22px; }.trace-span { position: relative; padding-bottom: 22px; }.trace-span__dot { background: #fff; border: 3px solid #22c55e; border-radius: 50%; height: 12px; left: -31px; position: absolute; top: 4px; width: 12px; }.trace-span__dot--error, .trace-span__dot--failed { border-color: #ef4444; }.trace-span h3 { color: #263452; margin: 0 0 5px; }.trace-span h3 small { background: #f1f5f9; border-radius: 4px; color: #64748b; font-size: 10px; font-weight: 500; margin-left: 8px; padding: 3px 6px; }.trace-span p { color: #71809b; font-size: 12px; margin: 0 0 9px; }.trace-span__facts { color: #64748b; display: flex; flex-wrap: wrap; font-size: 12px; gap: 12px; }.trace-span details { margin-top: 10px; }.trace-span summary { color: #4f46e5; cursor: pointer; font-size: 12px; }.trace-span pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 11px; max-height: 260px; overflow: auto; padding: 10px; white-space: pre-wrap; }
</style>
