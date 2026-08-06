<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getGraphRunDetail, listGraphRuns, type GraphRunDetail, type GraphRunSummary, type GraphType } from '@/api/graphRuns'

const activeType = ref<GraphType>('report_generation')
const route = useRoute()
const runs = ref<GraphRunSummary[]>([])
const selected = ref<GraphRunDetail | null>(null)
const loading = ref(false)
const detailLoading = ref(false)
const error = ref('')

const labels: Record<GraphType, string> = { report_generation: '生成报告', report_chat: '报告追问' }
const visibleRuns = computed(() => {
  const sessionId = typeof route.query.session_id === 'string' ? route.query.session_id : ''
  return runs.value.filter((run) => !sessionId || run.session_id === sessionId)
})
function formatTime(value: string | null | undefined) { return value ? value.slice(0, 19).replace('T', ' ') : '-' }
function eventLabel(event: GraphRunDetail['events'][number]) { return event.node_name || event.event_type }
function short(value: string | null) { return value && value.length > 120 ? `${value.slice(0, 120)}...` : value || '-' }

async function loadRuns() {
  loading.value = true; error.value = ''
  try { runs.value = await listGraphRuns(activeType.value) }
  catch (err) { error.value = err instanceof Error ? err.message : 'Graph 记录加载失败' }
  finally { loading.value = false }
}
async function openRun(run: GraphRunSummary) {
  detailLoading.value = true; error.value = ''
  try { selected.value = await getGraphRunDetail(run.graph_type, run.run_id) }
  catch (err) { error.value = err instanceof Error ? err.message : 'Graph 详情加载失败' }
  finally { detailLoading.value = false }
}
watch(activeType, loadRuns)
onMounted(() => {
  const queryType = route.query.type
  if (queryType === 'report_generation' || queryType === 'report_chat') activeType.value = queryType
  else void loadRuns()
})
</script>

<template>
  <div class="graph-page">
    <div class="graph-page__header"><div><h1>Graph 运行记录</h1><p>分别查看生成报告与报告追问的每次运行，以及完整节点执行链路。</p></div><button class="refresh-btn" type="button" @click="loadRuns">刷新</button></div>
    <div class="graph-tabs"><button v-for="(label, type) in labels" :key="type" type="button" :class="{ active: activeType === type }" @click="activeType = type as GraphType">{{ label }} <span>{{ activeType === type ? runs.length : '' }}</span></button></div>
    <div v-if="error" class="runtime-error">{{ error }}</div><div v-if="loading" class="runtime-empty">加载中...</div><div v-else-if="!visibleRuns.length" class="runtime-empty">暂无{{ labels[activeType] }}记录</div>
    <div v-else class="graph-list"><article v-for="run in visibleRuns" :key="run.run_id" class="graph-row" @click="openRun(run)"><div class="graph-row__top"><strong>{{ run.title }}</strong><span class="status-pill" :class="`status-pill--${run.status}`">{{ run.status }}</span><time>{{ formatTime(run.created_at) }}</time></div><div class="graph-row__meta"><span>{{ run.graph_name }}</span><code v-if="run.trace_id">{{ run.trace_id }}</code><span v-if="run.session_id">Session: {{ run.session_id }}</span></div><p>{{ short(run.summary) }}</p><button class="link-btn" type="button" @click.stop="openRun(run)">查看完整链路 →</button></article></div>

    <div v-if="selected || detailLoading" class="runtime-drawer" @click.self="selected = null"><section class="runtime-drawer__panel"><div class="runtime-drawer__header"><div><h2>{{ selected?.title || '加载 Graph 详情...' }}</h2><p v-if="selected">{{ selected.graph_name }} · {{ formatTime(selected.created_at) }}</p></div><button type="button" @click="selected = null">×</button></div><div v-if="detailLoading" class="runtime-empty">正在加载完整链路...</div><template v-else-if="selected"><div class="run-summary"><span>Trace <code>{{ selected.trace_id || '-' }}</code></span><span>状态 {{ selected.status }}</span><span>事件 {{ selected.events.length }}</span><span>Span {{ selected.traces.length }}</span></div><div class="run-section"><h3>执行链路</h3><div class="run-timeline"><article v-for="event in selected.events" :key="event.id" class="run-event"><i /><div><div class="run-event__title"><strong>{{ eventLabel(event) }}</strong><span>{{ event.status || 'event' }}</span><time>{{ formatTime(event.timestamp) }}</time></div><p>{{ event.message || event.event_type }}</p><small v-if="event.duration_ms">耗时 {{ event.duration_ms }} ms</small><details v-if="event.payload || event.error_message"><summary>查看事件数据</summary><pre>{{ JSON.stringify({ payload: event.payload, error: event.error_message }, null, 2) }}</pre></details></div></article></div></div><div class="run-section"><h3>输入</h3><pre>{{ JSON.stringify(selected.input, null, 2) }}</pre></div><div class="run-section"><h3>输出</h3><pre>{{ JSON.stringify(selected.output, null, 2) }}</pre></div><div v-if="selected.traces.length" class="run-section"><h3>Runtime Trace Spans</h3><pre>{{ JSON.stringify(selected.traces, null, 2) }}</pre></div></template></section></div>
  </div>
</template>

<style scoped>
.graph-page { max-width: 1500px; }.graph-page__header { align-items: center; display: flex; justify-content: space-between; margin-bottom: 22px; }.graph-page h1 { color: #14213d; font-size: 28px; margin: 0 0 6px; }.graph-page__header p { color: #71809b; margin: 0; }.refresh-btn { background: #172554; border: 0; border-radius: 8px; color: #fff; cursor: pointer; font-weight: 700; padding: 10px 18px; }.graph-tabs { border-bottom: 1px solid #dfe6f1; display: flex; gap: 6px; margin-bottom: 18px; }.graph-tabs button { background: transparent; border: 0; border-bottom: 3px solid transparent; color: #71809b; cursor: pointer; font-size: 14px; font-weight: 800; padding: 12px 18px; }.graph-tabs button.active { border-bottom-color: #6366f1; color: #3730a3; }.graph-tabs span { color: #94a3b8; font-size: 11px; }.graph-list { display: grid; gap: 12px; }.graph-row { background: #fff; border: 1px solid #dfe6f1; border-radius: 12px; cursor: pointer; padding: 18px 20px; }.graph-row:hover { border-color: #818cf8; }.graph-row__top { align-items: center; display: flex; gap: 12px; }.graph-row__top strong { color: #263452; }.graph-row__top time { color: #71809b; font-size: 12px; margin-left: auto; }.graph-row__meta { color: #71809b; display: flex; flex-wrap: wrap; font-size: 12px; gap: 14px; margin-top: 10px; }.graph-row__meta code { color: #4f46e5; }.graph-row p { color: #64748b; font-size: 13px; margin: 12px 0; }.link-btn { background: transparent; border: 0; color: #4f46e5; cursor: pointer; font-weight: 700; padding: 0; }.status-pill { background: #e2e8f0; border-radius: 999px; color: #475569; font-size: 11px; padding: 4px 9px; }.status-pill--success { background: #dcfce7; color: #166534; }.status-pill--failed { background: #fee2e2; color: #991b1b; }.status-pill--running { background: #fef3c7; color: #92400e; }.runtime-error { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #b91c1c; padding: 12px 16px; }.runtime-empty { color: #71809b; padding: 64px 20px; text-align: center; }.runtime-drawer { background: rgba(15,23,42,.42); inset: 0; position: fixed; z-index: 20; }.runtime-drawer__panel { background: #fff; height: 100%; max-width: 820px; overflow: auto; padding: 28px; position: absolute; right: 0; width: 68%; }.runtime-drawer__header { align-items: flex-start; display: flex; justify-content: space-between; }.runtime-drawer__header h2 { color: #14213d; margin: 0 0 5px; }.runtime-drawer__header p { color: #71809b; font-size: 12px; margin: 0; }.runtime-drawer__header button { background: none; border: 0; color: #64748b; cursor: pointer; font-size: 28px; }.run-summary { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; display: flex; flex-wrap: wrap; gap: 16px; margin: 22px 0; padding: 12px; }.run-summary span { color: #64748b; font-size: 12px; }.run-summary code { color: #4f46e5; }.run-section { margin-top: 24px; }.run-section h3 { color: #334155; font-size: 15px; margin: 0 0 10px; }.run-section > pre, .run-event pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 7px; font-size: 11px; max-height: 300px; overflow: auto; padding: 12px; white-space: pre-wrap; }.run-timeline { border-left: 2px solid #e2e8f0; margin-left: 6px; padding-left: 20px; }.run-event { padding-bottom: 19px; position: relative; }.run-event > i { background: #6366f1; border: 3px solid #fff; border-radius: 50%; box-shadow: 0 0 0 1px #a5b4fc; height: 10px; left: -27px; position: absolute; top: 4px; width: 10px; }.run-event__title { align-items: center; display: flex; gap: 10px; }.run-event__title strong { color: #263452; }.run-event__title span { color: #64748b; font-size: 11px; }.run-event__title time { color: #94a3b8; font-size: 11px; margin-left: auto; }.run-event p { color: #64748b; font-size: 13px; margin: 6px 0; }.run-event small { color: #64748b; }.run-event details { margin-top: 7px; }.run-event summary { color: #4f46e5; cursor: pointer; font-size: 12px; }
</style>
