<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  claimOperationMessage,
  getOperationMessageSummary,
  listOperationMessages,
  releaseOperationMessage,
  reopenOperationMessage,
  resolveOperationMessage,
  retryOperationMessage,
  type OperationMessage,
  type OperationMessageSummary,
  type OperationMessageTab,
} from '@/api/operationInbox'

const operatorId = 'operator_local'
const activeTab = ref<OperationMessageTab>('pending')
const messages = ref<OperationMessage[]>([])
const summary = ref<OperationMessageSummary>({ awaiting_review: 0, claimed: 0, reopened: 0, resolved: 0, failed: 0, processing: 0 })
const selected = ref<OperationMessage | null>(null)
const resolutionNote = ref('')
const loading = ref(false)
const actionId = ref<string | null>(null)
const error = ref('')
let pollTimer: ReturnType<typeof setInterval> | undefined

const tabs: Array<{ key: OperationMessageTab; label: string }> = [
  { key: 'pending', label: '待处理' },
  { key: 'mine', label: '我领取的' },
  { key: 'claimed', label: '全部已领取' },
  { key: 'resolved', label: '已解决' },
  { key: 'failed', label: '失败' },
]

const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || '消息')

function tabCount(tab: OperationMessageTab) {
  if (tab === 'pending') return summary.value.awaiting_review + summary.value.reopened
  return summary.value[tab === 'mine' ? 'claimed' : tab]
}

function formatTime(value: string | null) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

function priorityLabel(priority: number) {
  return priority >= 10 ? '高优先级' : priority > 0 ? '普通优先级' : '默认优先级'
}

async function loadMessages() {
  loading.value = true
  error.value = ''
  try {
    const itemsPromise = activeTab.value === 'pending'
      ? Promise.all([listOperationMessages({ status: 'awaiting_review' }), listOperationMessages({ status: 'reopened' })])
        .then(([awaitingReview, reopened]) => [...awaitingReview, ...reopened])
      : listOperationMessages({ status: activeTab.value, assignee_id: activeTab.value === 'mine' ? operatorId : undefined })
    const [items, counts] = await Promise.all([itemsPromise, getOperationMessageSummary()])
    messages.value = items.sort((left, right) => right.priority - left.priority || (left.created_at || '').localeCompare(right.created_at || ''))
    summary.value = counts
    if (selected.value) selected.value = messages.value.find((item) => item.id === selected.value?.id) || selected.value
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '待处理消息加载失败'
  } finally {
    loading.value = false
  }
}

async function runAction(message: OperationMessage, action: () => Promise<OperationMessage>) {
  actionId.value = message.id
  error.value = ''
  try {
    selected.value = await action()
    await loadMessages()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '消息操作失败'
  } finally {
    actionId.value = null
  }
}

function openMessage(message: OperationMessage) {
  selected.value = message
  resolutionNote.value = message.resolution_note || ''
}

function claim(message: OperationMessage) { void runAction(message, () => claimOperationMessage(message.id, { operator_id: operatorId })) }
function release(message: OperationMessage) { void runAction(message, () => releaseOperationMessage(message.id, { operator_id: operatorId })) }
function resolve(message: OperationMessage) { void runAction(message, () => resolveOperationMessage(message.id, { operator_id: operatorId, note: resolutionNote.value })) }
function reopen(message: OperationMessage) { void runAction(message, () => reopenOperationMessage(message.id, { operator_id: operatorId })) }
function retry(message: OperationMessage) { void runAction(message, () => retryOperationMessage(message.id, { operator_id: operatorId })) }

onMounted(() => {
  void loadMessages()
  pollTimer = setInterval(() => void loadMessages(), 10_000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="inbox-page">
    <header class="inbox-header">
      <div>
        <p class="inbox-eyebrow">OPERATION CONTROL / SHARED INBOX</p>
        <h1>待处理消息</h1>
        <p>以当前运营人员 <code>{{ operatorId }}</code> 的身份领取、处理和跟踪 AI 运行消息。</p>
      </div>
      <button class="button button--primary" type="button" :disabled="loading" @click="loadMessages">{{ loading ? '刷新中…' : '刷新' }}</button>
    </header>

    <p v-if="error" class="notice notice--error" role="alert">{{ error }}</p>

    <div class="inbox-tabs" role="tablist" aria-label="消息状态">
      <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key; void loadMessages()">
        {{ tab.label }} <span>{{ tabCount(tab.key) }}</span>
      </button>
    </div>
    <div class="inbox-toolbar"><span>{{ activeTabLabel }} · {{ messages.length }} 条</span><small>每 10 秒自动刷新</small></div>

    <div v-if="loading && !messages.length" class="empty-state">正在加载消息…</div>
    <div v-else-if="!messages.length" class="empty-state"><strong>暂无{{ activeTabLabel }}消息</strong><span>新产生的 AI 运行任务会在这里显示。</span></div>
    <section v-else class="message-list" aria-live="polite">
      <article v-for="message in messages" :key="message.id" class="message-card" @click="openMessage(message)">
        <div class="message-card__top"><span class="priority" :class="{ high: message.priority >= 10 }">{{ priorityLabel(message.priority) }}</span><span class="status">{{ message.status }}</span><time>{{ formatTime(message.created_at) }}</time></div>
        <h2>{{ message.input_text || '未提供任务输入' }}</h2>
        <p class="message-card__answer">{{ message.output_text || message.error_message || '任务正在处理中' }}</p>
        <div class="message-card__meta"><span>Session {{ message.runtime_session_id }}</span><span>Report {{ message.report_id ?? '-' }}</span><span>处理人：{{ message.assignee_id || '-' }}</span></div>
        <div class="message-card__actions" @click.stop>
          <button v-if="message.status === 'awaiting_review' || message.status === 'reopened'" class="button button--primary" type="button" :disabled="actionId === message.id" @click="claim(message)">领取</button>
          <button v-if="message.status === 'claimed' && message.assignee_id === operatorId" class="button" type="button" :disabled="actionId === message.id" @click="release(message)">释放</button>
          <button v-if="message.status === 'resolved'" class="button" type="button" :disabled="actionId === message.id" @click="reopen(message)">重新打开</button>
          <button v-if="message.status === 'failed'" class="button" type="button" :disabled="actionId === message.id" @click="retry(message)">重试</button>
          <button class="button" type="button" @click="openMessage(message)">查看详情</button>
        </div>
      </article>
    </section>

    <div v-if="selected" class="drawer-backdrop" @click.self="selected = null">
      <aside class="drawer" aria-label="消息详情">
        <header class="drawer__header"><div><p>MESSAGE DETAIL</p><h2>消息详情</h2><code>{{ selected.id }}</code></div><button type="button" aria-label="关闭详情" @click="selected = null">×</button></header>
        <div class="drawer__badges"><span class="status">{{ selected.status }}</span><span class="priority" :class="{ high: selected.priority >= 10 }">{{ priorityLabel(selected.priority) }}</span></div>
        <section class="drawer__section"><h3>任务内容</h3><p>{{ selected.input_text || '-' }}</p><pre>{{ selected.output_text || '-' }}</pre></section>
        <section class="drawer__section"><h3>处理信息</h3><dl><dt>Session</dt><dd>{{ selected.runtime_session_id }}</dd><dt>Report</dt><dd>{{ selected.report_id ?? '-' }}</dd><dt>优先级</dt><dd>{{ selected.priority }}</dd><dt>状态</dt><dd>{{ selected.status }} / AI {{ selected.ai_status || '-' }}</dd><dt>处理人</dt><dd>{{ selected.assignee_id || '-' }}</dd><dt>领取时间</dt><dd>{{ formatTime(selected.claimed_at) }}</dd><dt>租约到期</dt><dd>{{ formatTime(selected.lease_expires_at) }}</dd><dt>解决时间</dt><dd>{{ formatTime(selected.resolved_at) }}</dd><dt>创建 / 更新</dt><dd>{{ formatTime(selected.created_at) }} / {{ formatTime(selected.updated_at) }}</dd><dt>错误</dt><dd>{{ selected.error_message || '-' }}</dd><dt>解决备注</dt><dd>{{ selected.resolution_note || '-' }}</dd></dl></section>
        <section v-if="selected.status === 'claimed' && selected.assignee_id === operatorId" class="drawer__section"><h3>解决备注</h3><textarea v-model="resolutionNote" rows="4" placeholder="填写处理结论或补充说明" /><div class="drawer__actions"><button class="button button--primary" type="button" :disabled="actionId === selected.id" @click="resolve(selected)">标记解决</button><button class="button" type="button" :disabled="actionId === selected.id" @click="release(selected)">释放</button></div></section>
        <div class="drawer__actions"><RouterLink class="button" :to="{ path: '/platform/sessions', query: { session_id: selected.runtime_session_id } }">查看 Session</RouterLink><RouterLink class="button" :to="{ path: '/platform/traces', query: { session_id: selected.runtime_session_id } }">查看 Trace</RouterLink></div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.inbox-page { color: var(--theme-text); max-width: 1500px; }
.inbox-header { align-items: flex-end; display: flex; gap: 20px; justify-content: space-between; margin-bottom: 22px; }
.inbox-eyebrow, .drawer__header p { color: var(--theme-accent-strong); font: 700 10px ui-monospace, monospace; letter-spacing: .12em; margin: 0 0 8px; }
h1, h2, h3 { color: var(--theme-heading); margin-top: 0; }.inbox-header h1 { font-size: 28px; margin-bottom: 6px; }.inbox-header p:not(.inbox-eyebrow) { color: var(--theme-muted); margin: 0; }.inbox-header code { color: var(--theme-heading); }
.button { align-items: center; background: var(--theme-panel-soft); border: 1px solid var(--theme-border-strong); border-radius: 8px; color: var(--theme-heading); cursor: pointer; display: inline-flex; font: 700 11px inherit; justify-content: center; min-height: 32px; padding: 7px 12px; text-decoration: none; }.button--primary { background: var(--theme-accent); border-color: var(--theme-accent); color: var(--theme-accent-contrast); }.button:disabled { cursor: wait; opacity: .6; }
.notice { border-radius: 8px; margin: 0 0 14px; padding: 11px 14px; }.notice--error { background: var(--theme-danger-soft); border: 1px solid var(--theme-danger-text); color: var(--theme-danger-text); }
.inbox-tabs { border-bottom: 1px solid var(--theme-border); display: flex; gap: 6px; overflow-x: auto; }.inbox-tabs button { background: transparent; border: 0; border-bottom: 3px solid transparent; color: var(--theme-muted); cursor: pointer; font: 800 13px inherit; padding: 12px 16px; white-space: nowrap; }.inbox-tabs button.active { border-bottom-color: var(--theme-accent); color: var(--theme-accent-strong); }.inbox-tabs span { background: var(--theme-accent-soft); border-radius: 999px; font-size: 10px; margin-left: 5px; padding: 3px 6px; }
.inbox-toolbar { color: var(--theme-heading); display: flex; justify-content: space-between; padding: 17px 2px; }.inbox-toolbar small { color: var(--theme-muted); }.empty-state { align-items: center; background: var(--theme-panel-solid); border: 1px dashed var(--theme-border-strong); border-radius: 12px; color: var(--theme-muted); display: flex; flex-direction: column; gap: 8px; padding: 75px 20px; text-align: center; }.empty-state strong { color: var(--theme-heading); }
.message-list { display: grid; gap: 12px; }.message-card { background: var(--theme-panel-solid); border: 1px solid var(--theme-border); border-radius: 12px; box-shadow: var(--theme-shadow-soft); cursor: pointer; padding: 18px 20px; }.message-card__top, .message-card__meta, .message-card__actions, .drawer__badges, .drawer__actions { align-items: center; display: flex; flex-wrap: wrap; gap: 8px; }.message-card__top time { color: var(--theme-muted); font-size: 11px; margin-left: auto; }.priority, .status { background: var(--theme-accent-soft); border-radius: 999px; color: var(--theme-accent-strong); font-size: 10px; padding: 4px 8px; }.priority.high { background: var(--theme-danger-soft); color: var(--theme-danger-text); }.message-card h2 { font-size: 15px; margin: 13px 0 7px; }.message-card__answer { color: var(--theme-muted); font-size: 12px; line-height: 1.65; margin: 0; max-height: 42px; overflow: hidden; }.message-card__meta { color: var(--theme-muted); font-size: 10px; margin-top: 13px; }.message-card__actions { margin-top: 15px; }
.drawer-backdrop { background: rgba(15, 23, 42, .42); inset: 0; position: fixed; z-index: 50; }.drawer { background: var(--theme-panel-solid); border-left: 1px solid var(--theme-border); box-shadow: var(--theme-shadow); height: 100%; max-width: 700px; overflow: auto; padding: 28px; position: absolute; right: 0; width: 55%; }.drawer__header { align-items: flex-start; display: flex; justify-content: space-between; }.drawer__header h2 { font-size: 22px; margin: 0 0 4px; }.drawer__header code { color: var(--theme-muted); font-size: 11px; }.drawer__header button { background: transparent; border: 0; color: var(--theme-muted); cursor: pointer; font-size: 28px; }.drawer__badges { margin: 24px 0 4px; }.drawer__section { border-top: 1px solid var(--theme-border); margin-top: 20px; padding-top: 18px; }.drawer__section h3 { font-size: 13px; margin-bottom: 10px; }.drawer__section p, .drawer__section dd { font-size: 12px; line-height: 1.65; overflow-wrap: anywhere; }.drawer__section pre { background: var(--theme-panel-soft); border: 1px solid var(--theme-border); border-radius: 8px; font-size: 12px; max-height: 220px; overflow: auto; padding: 12px; white-space: pre-wrap; }.drawer__section dl { display: grid; gap: 10px 18px; grid-template-columns: 100px 1fr; }.drawer__section dt { color: var(--theme-muted); font-size: 12px; }.drawer__section dd { color: var(--theme-heading); margin: 0; }.drawer__section textarea { background: var(--theme-panel-soft); border: 1px solid var(--theme-border); border-radius: 8px; box-sizing: border-box; color: var(--theme-text); font: inherit; padding: 10px; resize: vertical; width: 100%; }.drawer__actions { margin-top: 16px; }
@media (max-width: 700px) { .inbox-header { align-items: flex-start; flex-direction: column; }.drawer { max-width: none; width: 88%; } }
</style>
