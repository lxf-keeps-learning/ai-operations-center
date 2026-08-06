<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { cancelRuntimeSession, listRuntimeSessions, streamRuntimeChat, type RuntimeSession } from '@/api/runtime'

const sessions = ref<RuntimeSession[]>([])
const selected = ref<RuntimeSession | null>(null)
const loading = ref(false)
const error = ref('')
const retryingId = ref<string | null>(null)
const cancellingId = ref<string | null>(null)
const route = useRoute()

function queryValue(key: string) {
  const value = route.query[key]
  return typeof value === 'string' ? value : ''
}

const statusFilter = ref(queryValue('status'))
const dateFrom = ref(queryValue('date_from'))
const dateTo = ref(queryValue('date_to'))
const pageSize = ref(Number(queryValue('page_size')) || 50)

const selectedReportId = computed(() => {
  const value = selected.value?.context?.report_id || selected.value?.context?.record_id
  return typeof value === 'number' || typeof value === 'string' ? String(value) : null
})

function formatTime(value: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

async function loadSessions() {
  loading.value = true
  error.value = ''
  try {
    sessions.value = await listRuntimeSessions({
      status: statusFilter.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      page_size: pageSize.value,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Session 列表加载失败'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  statusFilter.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  pageSize.value = 50
  void loadSessions()
}

onMounted(() => void loadSessions())

function isRunning(session: RuntimeSession) {
  return session.status === 'running' || session.status === 'cancel_requested'
}

function canRetry(session: RuntimeSession) {
  return session.status === 'failed' || session.status === 'cancelled'
}

async function cancelSession(session: RuntimeSession) {
  if (!isRunning(session) || cancellingId.value) return
  cancellingId.value = session.id
  error.value = ''
  try {
    const updated = await cancelRuntimeSession(session.id)
    sessions.value = sessions.value.map((item) => item.id === session.id ? updated : item)
    if (selected.value?.id === session.id) selected.value = updated
  } catch (err) {
    error.value = err instanceof Error ? err.message : '取消 Session 失败'
  } finally {
    cancellingId.value = null
  }
}

function retrySession(session: RuntimeSession) {
  if (!canRetry(session) || retryingId.value) return
  retryingId.value = session.id
  error.value = ''
  streamRuntimeChat(
    {
      message: session.input_text,
      conversation_id: session.conversation_id,
      user_id: session.user_id,
      retry_of_session_id: session.id,
    },
    {
      onStarted() {},
      onDelta() {},
      onCompleted() { void loadSessions() },
      onCancelled() { error.value = '重试任务被取消' },
      onError(err) { retryingId.value = null; error.value = err.message },
      onClose() { retryingId.value = null; void loadSessions() },
    },
  )
}
</script>

<template>
  <div class="runtime-page">
    <div class="runtime-page__header">
      <div>
        <h1>Session 运行记录</h1>
        <p>查看每次对话、报告追问和运行任务的输入、输出与状态。</p>
      </div>
      <button class="refresh-btn" type="button" @click="loadSessions">刷新</button>
    </div>

    <form class="runtime-filters" @submit.prevent="loadSessions">
      <label>状态<select v-model="statusFilter"><option value="">全部</option><option value="running">运行中</option><option value="success">已完成</option><option value="failed">失败</option><option value="cancelled">已取消</option></select></label>
      <label>开始日期<input v-model="dateFrom" type="date" /></label>
      <label>结束日期<input v-model="dateTo" type="date" /></label>
      <label>每页<select v-model.number="pageSize"><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select></label>
      <button class="link-btn" type="submit">筛选</button><button class="link-btn" type="button" @click="resetFilters">重置</button>
    </form>

    <div v-if="error" class="runtime-error">{{ error }}</div>
    <div v-if="loading" class="runtime-empty">加载中...</div>
    <div v-else-if="!sessions.length" class="runtime-empty">暂无 Session 运行记录</div>
    <div v-else class="runtime-card runtime-table-wrap">
      <table class="runtime-table">
        <thead><tr><th>Session ID</th><th>类型</th><th>输入</th><th>状态</th><th>创建时间</th><th>快捷操作</th></tr></thead>
        <tbody>
          <tr v-for="session in sessions" :key="session.id">
            <td><code>{{ session.id }}</code></td>
            <td>{{ session.task_type || 'conversation' }}</td>
            <td class="runtime-cell-truncate">{{ session.input_text }}</td>
            <td><span class="status-pill" :class="`status-pill--${session.status}`">{{ session.status }}</span></td>
            <td>{{ formatTime(session.created_at) }}</td>
            <td>
              <div class="runtime-actions">
                <button class="link-btn" type="button" @click="selected = session">详情</button>
                <RouterLink class="link-btn" :to="{ path: '/platform/traces', query: { session_id: session.id } }">Trace</RouterLink>
                <RouterLink class="link-btn" :to="{ path: '/platform/graphs', query: { session_id: session.id } }">Graph</RouterLink>
                <button v-if="canRetry(session)" class="link-btn" type="button" :disabled="retryingId === session.id" @click="retrySession(session)">
                  {{ retryingId === session.id ? '重试中' : '重试' }}
                </button>
                <button v-else-if="isRunning(session)" class="link-btn link-btn--danger" type="button" :disabled="cancellingId === session.id" @click="cancelSession(session)">
                  {{ cancellingId === session.id ? '取消中' : '取消' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="selected" class="runtime-drawer" @click.self="selected = null">
      <section class="runtime-drawer__panel">
        <div class="runtime-drawer__header"><h2>Session 详情</h2><button type="button" @click="selected = null">×</button></div>
        <dl class="runtime-detail-grid">
          <dt>Session ID</dt><dd><code>{{ selected.id }}</code></dd>
          <dt>Conversation</dt><dd><code>{{ selected.conversation_id }}</code></dd>
          <dt>用户</dt><dd>{{ selected.user_id }}</dd>
          <dt>状态</dt><dd>{{ selected.status }}</dd>
          <dt>开始时间</dt><dd>{{ formatTime(selected.started_at) }}</dd>
          <dt>结束时间</dt><dd>{{ formatTime(selected.finished_at) }}</dd>
        </dl>
        <h3>输入</h3><pre>{{ selected.input_text }}</pre>
        <h3>输出</h3><pre>{{ selected.output_text || '-' }}</pre>
        <h3 v-if="selected.error_message">错误</h3><pre v-if="selected.error_message" class="runtime-pre-error">{{ selected.error_message }}</pre>
        <div class="runtime-actions runtime-actions--drawer">
          <RouterLink class="drawer-action" :to="{ path: '/platform/conversations', query: { conversation_id: selected.conversation_id } }">查看 Conversation</RouterLink>
          <RouterLink class="drawer-action" :to="{ path: '/platform/traces', query: { session_id: selected.id } }">查看 Trace</RouterLink>
          <RouterLink class="drawer-action" :to="{ path: '/platform/graphs', query: { session_id: selected.id } }">查看 Graph</RouterLink>
          <RouterLink v-if="selectedReportId" class="drawer-action" :to="{ path: '/operation', query: { record_id: selectedReportId } }">查看报告</RouterLink>
          <span v-else class="drawer-action drawer-action--disabled" title="当前 Session 未关联报告">未关联报告</span>
          <button v-if="canRetry(selected)" class="drawer-action" type="button" @click="retrySession(selected)">重新执行</button>
          <button v-if="isRunning(selected)" class="drawer-action drawer-action--danger" type="button" @click="cancelSession(selected)">取消运行</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.runtime-page { max-width: 1500px; }
.runtime-page__header { align-items: center; display: flex; justify-content: space-between; margin-bottom: 24px; }
h1 { color: #14213d; font-size: 28px; margin: 0 0 6px; }
.runtime-page__header p { color: #71809b; margin: 0; }
.refresh-btn, .link-btn { border: 0; cursor: pointer; font-weight: 700; }
.refresh-btn { background: #172554; border-radius: 8px; color: #fff; padding: 10px 18px; }
.runtime-filters { align-items: end; display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }.runtime-filters label { color: #71809b; display: grid; font-size: 12px; gap: 5px; }.runtime-filters input, .runtime-filters select { border: 1px solid #d7dfeb; border-radius: 7px; color: #263452; font: inherit; min-height: 36px; padding: 0 9px; }
.runtime-card { background: #fff; border: 1px solid #dfe6f1; border-radius: 12px; }
.runtime-table-wrap { overflow: auto; }
.runtime-table { border-collapse: collapse; min-width: 920px; width: 100%; }
.runtime-table th, .runtime-table td { border-bottom: 1px solid #edf1f7; padding: 14px 16px; text-align: left; }
.runtime-table th { background: #f8fafc; color: #64748b; font-size: 12px; }
.runtime-table td { color: #334155; font-size: 13px; }
.runtime-actions { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }
.runtime-actions--drawer { border-top: 1px solid #e2e8f0; margin-top: 24px; padding-top: 18px; }
.runtime-table code, code { color: #4f46e5; font-family: ui-monospace, monospace; font-size: 12px; }
.runtime-cell-truncate { max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-pill { background: #e2e8f0; border-radius: 999px; color: #475569; display: inline-block; font-size: 11px; padding: 4px 9px; }
.status-pill--success { background: #dcfce7; color: #166534; }.status-pill--failed { background: #fee2e2; color: #991b1b; }.status-pill--running { background: #fef3c7; color: #92400e; }.status-pill--cancel_requested { background: #e0e7ff; color: #4338ca; }
.link-btn { background: transparent; color: #4f46e5; }
.link-btn:disabled, .drawer-action:disabled { cursor: wait; opacity: .55; }
.link-btn--danger, .drawer-action--danger { color: #b91c1c; }
.drawer-action { background: #eef2ff; border: 0; border-radius: 7px; color: #4338ca; cursor: pointer; font-size: 12px; font-weight: 700; padding: 8px 10px; text-decoration: none; }
.drawer-action--disabled { background: #f1f5f9; color: #94a3b8; cursor: not-allowed; }
.runtime-error { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #b91c1c; margin-bottom: 16px; padding: 12px 16px; }
.runtime-empty { color: #71809b; padding: 64px 20px; text-align: center; }
.runtime-drawer { background: rgba(15, 23, 42, .42); inset: 0; position: fixed; z-index: 20; }
.runtime-drawer__panel { background: #fff; height: 100%; max-width: 620px; overflow: auto; padding: 28px; position: absolute; right: 0; width: 52%; }
.runtime-drawer__header { align-items: center; display: flex; justify-content: space-between; }.runtime-drawer__header h2 { color: #14213d; margin: 0; }.runtime-drawer__header button { background: none; border: 0; color: #64748b; cursor: pointer; font-size: 28px; }
.runtime-detail-grid { display: grid; gap: 10px 18px; grid-template-columns: 120px 1fr; margin: 28px 0; }.runtime-detail-grid dt { color: #64748b; }.runtime-detail-grid dd { margin: 0; overflow-wrap: anywhere; }
h3 { color: #334155; font-size: 14px; margin: 22px 0 8px; } pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; color: #334155; padding: 14px; white-space: pre-wrap; }.runtime-pre-error { color: #b91c1c; }
</style>
