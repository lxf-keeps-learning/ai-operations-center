<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  claimOperationMessage,
  getOperationMessageSummary,
  listOperationMessages,
  releaseOperationMessage,
  resolveOperationMessage,
  type OperationMessage,
} from '@/api/operationInbox'

type InboxTab = 'awaiting_review' | 'mine' | 'claimed' | 'resolved' | 'failed'

const operatorId = 'operator_demo'
const activeTab = ref<InboxTab>('awaiting_review')
const messages = ref<OperationMessage[]>([])
const summary = ref({ awaiting_review: 0, claimed: 0, resolved: 0, failed: 0, processing: 0 })
const selected = ref<OperationMessage | null>(null)
const resolutionNote = ref('')
const loading = ref(false)
const actionId = ref<string | null>(null)
const error = ref('')
let pollTimer: ReturnType<typeof setInterval> | undefined

const tabs: Array<{ key: InboxTab; label: string; countKey: keyof typeof summary.value }> = [
  { key: 'awaiting_review', label: '待领取', countKey: 'awaiting_review' },
  { key: 'mine', label: '我的处理中', countKey: 'claimed' },
  { key: 'claimed', label: '全部处理中', countKey: 'claimed' },
  { key: 'resolved', label: '已完成', countKey: 'resolved' },
  { key: 'failed', label: '异常', countKey: 'failed' },
]

const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || '消息')

function formatTime(value: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function priorityLabel(priority: number) {
  return priority >= 10 ? '高优先级' : '普通'
}

async function loadInbox() {
  loading.value = true
  error.value = ''
  try {
    const [items, counts] = await Promise.all([
      listOperationMessages({ status: activeTab.value, assignee_id: activeTab.value === 'mine' ? operatorId : undefined }),
      getOperationMessageSummary(),
    ])
    messages.value = items
    summary.value = counts
    if (selected.value) selected.value = items.find((item) => item.id === selected.value?.id) || selected.value
  } catch (err) {
    error.value = err instanceof Error ? err.message : '待处理消息加载失败'
  } finally {
    loading.value = false
  }
}

async function runAction(id: string, action: () => Promise<OperationMessage>) {
  actionId.value = id
  error.value = ''
  try {
    const updated = await action()
    selected.value = updated
    await loadInbox()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '消息操作失败'
  } finally {
    actionId.value = null
  }
}

function claim(message: OperationMessage) { void runAction(message.id, () => claimOperationMessage(message.id, operatorId)) }
function release(message: OperationMessage) { void runAction(message.id, () => releaseOperationMessage(message.id, operatorId)) }
function resolve(message: OperationMessage) { void runAction(message.id, () => resolveOperationMessage(message.id, operatorId, resolutionNote.value)) }

function openMessage(message: OperationMessage) {
  selected.value = message
  resolutionNote.value = message.resolution_note || ''
}

onMounted(() => {
  void loadInbox()
  pollTimer = setInterval(() => void loadInbox(), 10000)
})
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <div class="inbox-page">
    <header class="inbox-header"><div><div class="inbox-eyebrow">OPERATION CONTROL / SHARED INBOX</div><h1>待处理消息</h1><p>运营人员共享领取和处理 AI 深度解答任务。</p></div><button class="refresh-button" type="button" :disabled="loading" @click="loadInbox">{{ loading ? '刷新中…' : '刷新' }}</button></header>
    <div v-if="error" class="inbox-error">{{ error }}</div>
    <section class="inbox-tabs" role="tablist" aria-label="消息状态">
      <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key; void loadInbox()">{{ tab.label }} <span>{{ summary[tab.countKey] }}</span></button>
    </section>
    <section class="inbox-toolbar"><span>{{ activeTabLabel }} · {{ messages.length }} 条</span><small>每 10 秒自动刷新</small></section>
    <div v-if="loading && !messages.length" class="inbox-empty">正在加载消息…</div>
    <div v-else-if="!messages.length" class="inbox-empty"><strong>暂无{{ activeTabLabel }}消息</strong><span>新的 AI 运行任务进入系统后会显示在这里。</span></div>
    <section v-else class="message-list">
      <article v-for="message in messages" :key="message.id" class="message-card" @click="openMessage(message)">
        <div class="message-card__top"><span class="priority" :class="{ high: message.priority >= 10 }">{{ priorityLabel(message.priority) }}</span><span class="message-status">{{ message.status }}</span><time>{{ formatTime(message.created_at) }}</time></div>
        <h2>{{ message.input_text }}</h2><p class="message-card__answer">{{ message.output_text || message.error_message || '任务正在处理中' }}</p>
        <div class="message-card__meta"><span>{{ message.task_type || 'conversation' }}</span><span>Session {{ message.runtime_session_id }}</span><span v-if="message.assignee_id">处理人：{{ message.assignee_id }}</span></div>
        <div class="message-card__actions" @click.stop><button v-if="message.status === 'awaiting_review'" type="button" class="action-primary" :disabled="actionId === message.id" @click="claim(message)">领取处理</button><button v-if="message.status === 'claimed' && message.assignee_id === operatorId" type="button" class="action-secondary" :disabled="actionId === message.id" @click="release(message)">释放</button><button type="button" class="action-secondary" @click="openMessage(message)">查看详情</button></div>
      </article>
    </section>

    <div v-if="selected" class="inbox-drawer" @click.self="selected = null"><section class="inbox-drawer__panel"><header class="drawer-header"><div><span>MESSAGE DETAIL</span><h2>消息详情</h2><p>{{ selected.runtime_session_id }}</p></div><button type="button" aria-label="关闭详情" @click="selected = null">×</button></header><div class="drawer-status"><span class="message-status">{{ selected.status }}</span><span>{{ priorityLabel(selected.priority) }}</span></div><section class="drawer-section"><h3>用户问题</h3><p>{{ selected.input_text }}</p></section><section class="drawer-section"><h3>AI 输出</h3><pre>{{ selected.output_text || selected.error_message || '暂无输出' }}</pre></section><section class="drawer-section"><h3>运行信息</h3><dl><dt>任务类型</dt><dd>{{ selected.task_type || '-' }}</dd><dt>Session</dt><dd>{{ selected.runtime_session_id }}</dd><dt>Trace</dt><dd>{{ selected.trace_id || '-' }}</dd><dt>创建时间</dt><dd>{{ formatTime(selected.created_at) }}</dd></dl></section><section v-if="selected.status === 'claimed' && selected.assignee_id === operatorId" class="drawer-section"><h3>处理备注</h3><textarea v-model="resolutionNote" rows="4" placeholder="填写处理结论或补充说明" /><div class="drawer-actions"><button type="button" class="action-primary" :disabled="actionId === selected.id" @click="resolve(selected)">标记完成</button><button type="button" class="action-secondary" :disabled="actionId === selected.id" @click="release(selected)">释放消息</button></div></section><div class="drawer-actions"><RouterLink class="action-secondary" :to="{ path: '/platform/sessions', query: { session_id: selected.runtime_session_id } }">查看 Session</RouterLink><RouterLink class="action-secondary" :to="{ path: '/platform/traces', query: { session_id: selected.runtime_session_id } }">查看 Trace</RouterLink><RouterLink class="action-secondary" :to="{ path: '/platform/graphs', query: { session_id: selected.runtime_session_id } }">查看 Graph</RouterLink></div></section></div>
  </div>
</template>

<style scoped>
.inbox-page { max-width: 1500px; }.inbox-header { align-items: flex-end; display: flex; justify-content: space-between; margin-bottom: 22px; }.inbox-eyebrow { color: var(--theme-accent-strong); font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: .12em; margin-bottom: 9px; }.inbox-page h1 { color: var(--theme-heading); font-size: 28px; margin: 0 0 6px; }.inbox-header p { color: var(--theme-muted); margin: 0; }.refresh-button, .action-primary, .action-secondary { align-items: center; appearance: none; border-radius: 8px; cursor: pointer; display: inline-flex; font: inherit; font-size: 11px; font-weight: 700; justify-content: center; min-height: 32px; padding: 7px 12px; text-decoration: none; }.refresh-button, .action-primary { background: var(--theme-accent); border: 1px solid var(--theme-accent); color: var(--theme-accent-contrast); }.refresh-button:disabled, .action-primary:disabled { cursor: wait; opacity: .55; }.action-secondary { background: var(--theme-panel-soft); border: 1px solid var(--theme-border-strong); color: var(--theme-heading); }.action-secondary:hover, .refresh-button:hover, .action-primary:hover { box-shadow: var(--theme-shadow-soft); transform: translateY(-1px); }.inbox-error { background: var(--theme-danger-soft); border: 1px solid var(--theme-danger-text); border-radius: 8px; color: var(--theme-danger-text); margin-bottom: 15px; padding: 11px 14px; }.inbox-tabs { border-bottom: 1px solid var(--theme-border); display: flex; gap: 6px; overflow-x: auto; }.inbox-tabs button { background: transparent; border: 0; border-bottom: 3px solid transparent; color: var(--theme-muted); cursor: pointer; font: inherit; font-size: 13px; font-weight: 800; padding: 12px 16px; white-space: nowrap; }.inbox-tabs button.active { border-bottom-color: var(--theme-accent); color: var(--theme-accent-strong); }.inbox-tabs span { background: var(--theme-accent-soft); border-radius: 999px; color: var(--theme-accent-strong); font-size: 10px; margin-left: 5px; padding: 3px 6px; }.inbox-toolbar { align-items: center; color: var(--theme-heading); display: flex; justify-content: space-between; padding: 17px 2px; }.inbox-toolbar small { color: var(--theme-muted); }.inbox-empty { align-items: center; background: var(--theme-panel-solid); border: 1px dashed var(--theme-border-strong); border-radius: 12px; color: var(--theme-muted); display: flex; flex-direction: column; gap: 8px; padding: 75px 20px; text-align: center; }.inbox-empty strong { color: var(--theme-heading); }.message-list { display: grid; gap: 12px; }.message-card { background: var(--theme-panel-solid); border: 1px solid var(--theme-border); border-radius: 12px; box-shadow: var(--theme-shadow-soft); cursor: pointer; padding: 18px 20px; transition: border-color .16s ease, transform .16s ease, box-shadow .16s ease; }.message-card:hover { border-color: var(--theme-border-strong); box-shadow: var(--theme-shadow); transform: translateY(-1px); }.message-card__top, .message-card__meta { align-items: center; display: flex; flex-wrap: wrap; gap: 10px; }.message-card__top time { color: var(--theme-muted); font-size: 11px; margin-left: auto; }.priority, .message-status { background: var(--theme-accent-soft); border-radius: 999px; color: var(--theme-accent-strong); font-size: 10px; padding: 4px 8px; }.priority.high { background: var(--theme-danger-soft); color: var(--theme-danger-text); }.message-card h2 { color: var(--theme-heading); font-size: 15px; line-height: 1.5; margin: 13px 0 7px; }.message-card__answer { color: var(--theme-muted); font-size: 12px; line-height: 1.65; margin: 0; max-height: 42px; overflow: hidden; }.message-card__meta { color: var(--theme-muted); font-size: 10px; margin-top: 13px; }.message-card__actions { display: flex; gap: 8px; margin-top: 15px; }.inbox-drawer { background: rgba(15,23,42,.42); inset: 0; position: fixed; z-index: 50; }.inbox-drawer__panel { background: var(--theme-panel-solid); border-left: 1px solid var(--theme-border); box-shadow: var(--theme-shadow); height: 100%; max-width: 700px; overflow: auto; padding: 28px; position: absolute; right: 0; width: 55%; }.drawer-header { align-items: flex-start; display: flex; justify-content: space-between; }.drawer-header span { color: var(--theme-accent-strong); font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: .1em; }.drawer-header h2 { color: var(--theme-heading); font-size: 22px; margin: 7px 0 4px; }.drawer-header p { color: var(--theme-muted); font-size: 11px; margin: 0; }.drawer-header button { background: transparent; border: 0; color: var(--theme-muted); cursor: pointer; font-size: 28px; }.drawer-status { display: flex; gap: 10px; margin: 25px 0 5px; }.drawer-section { border-top: 1px solid var(--theme-border); margin-top: 20px; padding-top: 18px; }.drawer-section h3 { color: var(--theme-heading); font-size: 13px; margin: 0 0 10px; }.drawer-section p { color: var(--theme-text); font-size: 13px; line-height: 1.7; }.drawer-section pre { background: var(--theme-panel-soft); border: 1px solid var(--theme-border); border-radius: 8px; color: var(--theme-text); font-size: 12px; line-height: 1.65; max-height: 280px; overflow: auto; padding: 12px; white-space: pre-wrap; }.drawer-section dl { display: grid; gap: 10px 18px; grid-template-columns: 90px 1fr; }.drawer-section dt { color: var(--theme-muted); font-size: 12px; }.drawer-section dd { color: var(--theme-heading); font-size: 12px; margin: 0; overflow-wrap: anywhere; }.drawer-section textarea { background: var(--theme-panel-soft); border: 1px solid var(--theme-border); border-radius: 8px; color: var(--theme-text); font: inherit; font-size: 12px; padding: 10px; resize: vertical; width: 100%; }.drawer-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
@media (max-width: 700px) { .inbox-header { align-items: flex-start; flex-direction: column; gap: 15px; }.inbox-drawer__panel { max-width: none; width: 88%; } }
</style>
