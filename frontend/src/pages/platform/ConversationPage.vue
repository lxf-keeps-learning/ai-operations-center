<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  getRuntimeConversation,
  listRuntimeConversations,
  streamRuntimeChat,
  type RuntimeChatStreamCompleted,
  type RuntimeConversation,
  type RuntimeConversationDetail,
} from '@/api/runtime'

interface Message { role: 'user' | 'assistant'; content: string; sessionId?: string | null; traceId?: string | null }

const conversations = ref<RuntimeConversation[]>([])
const selectedConversation = ref<RuntimeConversationDetail | null>(null)
const messages = ref<Message[]>([])
const currentConversationId = ref<string | null>(null)
const lastSessionId = ref<string | null>(null)
const lastTraceId = ref<string | null>(null)
const input = ref('')
const loading = ref(false)
const loadingList = ref(false)
const error = ref('')
const messageBox = ref<HTMLElement | null>(null)
const route = useRoute()

const activeTitle = computed(() => selectedConversation.value?.title || '新建对话')
const activeStatus = computed(() => selectedConversation.value?.status || '未开始')

function formatTime(value: string | null | undefined) { return value ? value.slice(0, 16).replace('T', ' ') : '-' }
function resetChat() {
  currentConversationId.value = null; selectedConversation.value = null; messages.value = []; lastSessionId.value = null; lastTraceId.value = null; error.value = ''
}
async function loadConversations() {
  loadingList.value = true
  try { conversations.value = await listRuntimeConversations() }
  catch (err) { error.value = err instanceof Error ? err.message : '对话列表加载失败' }
  finally { loadingList.value = false }
}
async function selectConversation(item: RuntimeConversation) {
  error.value = ''
  try {
    const detail = await getRuntimeConversation(item.id)
    selectedConversation.value = detail; currentConversationId.value = detail.id
    messages.value = detail.sessions.flatMap((session) => [
      { role: 'user' as const, content: session.input_text, sessionId: session.id },
      ...(session.output_text ? [{ role: 'assistant' as const, content: session.output_text, sessionId: session.id }] : []),
    ])
    const latest = detail.sessions[detail.sessions.length - 1]
    lastSessionId.value = latest?.id || null
  } catch (err) { error.value = err instanceof Error ? err.message : '对话详情加载失败' }
}
function sendMessage() {
  const text = input.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''; loading.value = true; error.value = ''
  const assistant: Message = { role: 'assistant', content: '' }
  messages.value.push(assistant)
  void nextTick(() => messageBox.value?.scrollTo({ top: messageBox.value.scrollHeight, behavior: 'smooth' }))
  streamRuntimeChat(
    { message: text, conversation_id: currentConversationId.value },
    {
      onStarted(traceId) { lastTraceId.value = traceId },
      onDelta(delta) { assistant.content += delta },
      onCompleted(event: RuntimeChatStreamCompleted) {
        currentConversationId.value = event.conversation_id; lastSessionId.value = event.session_id; lastTraceId.value = event.trace_id; assistant.content = event.answer
      },
      onError(err) { error.value = err.message },
      onClose() { loading.value = false; void loadConversations(); void nextTick(() => messageBox.value?.scrollTo({ top: messageBox.value.scrollHeight, behavior: 'smooth' })) },
    },
  )
}
onMounted(async () => {
  await loadConversations()
  const conversationId = typeof route.query.conversation_id === 'string' ? route.query.conversation_id : ''
  const target = conversations.value.find((item) => item.id === conversationId)
  if (target) await selectConversation(target)
})
</script>

<template>
  <div class="conversation-page">
    <aside class="conversation-list">
      <div class="conversation-list__header"><div><strong>对话</strong><small>Agent 工作台</small></div><button type="button" aria-label="新建对话" @click="resetChat">＋</button></div>
      <div v-if="loadingList" class="conversation-list__empty">加载中...</div>
      <div v-else-if="!conversations.length" class="conversation-list__empty">暂无历史对话<br><small>发送第一条消息开始</small></div>
      <button v-for="item in conversations" :key="item.id" type="button" class="conversation-item" :class="{ active: currentConversationId === item.id }" @click="selectConversation(item)"><strong>{{ item.title || '未命名对话' }}</strong><span>{{ item.biz_type || 'chat' }} · {{ formatTime(item.updated_at) }}</span></button>
    </aside>

    <section class="conversation-main">
      <header class="conversation-main__header"><div><h1>{{ activeTitle }}</h1><p>{{ currentConversationId || '尚未创建 Conversation' }}</p></div><span class="conversation-state">{{ activeStatus }}</span></header>
      <div ref="messageBox" class="conversation-messages"><div v-if="!messages.length" class="conversation-empty"><div class="conversation-empty__icon">✦</div><h2>开始一次 Agent 对话</h2><p>输入问题后，系统会创建 Conversation、Session，并记录完整 Trace。</p></div><article v-for="(message, index) in messages" :key="index" class="message" :class="`message--${message.role}`"><div class="message__role">{{ message.role === 'user' ? '你' : 'AI Agent' }}</div><div class="message__body">{{ message.content || (loading && index === messages.length - 1 ? '正在思考...' : '') }}</div></article></div>
      <p v-if="error" class="conversation-error">{{ error }}</p>
      <form class="conversation-input" @submit.prevent="sendMessage"><textarea v-model="input" rows="3" placeholder="向 Agent 提问，例如：请分析当前运营数据中的主要风险" :disabled="loading" @keydown.enter.exact.prevent="sendMessage" /><button type="submit" :disabled="loading || !input.trim()">{{ loading ? '生成中...' : '发送' }}</button></form>
    </section>

    <aside class="conversation-inspector"><h2>本次运行</h2><p class="inspector-subtitle">消息发送后自动关联运行信息</p><div class="inspector-card"><span>Agent</span><strong>Runtime Chat</strong><small>当前默认运行时</small></div><div class="inspector-card"><span>Session</span><code>{{ lastSessionId || '-' }}</code><small>单次消息执行记录</small></div><div class="inspector-card"><span>Trace</span><code>{{ lastTraceId || '-' }}</code><small>完整执行链路</small></div><div class="inspector-card"><span>Prompt</span><strong>默认 Prompt</strong><small>可从 Prompt 策略中心管理</small></div><div class="inspector-hint">每次回答都会生成一个新的 Session 和 Trace，可在左侧对应页面查看详情。</div></aside>
  </div>
</template>

<style scoped>
.conversation-page { background: #f8fafc; border: 1px solid #dfe6f1; border-radius: 14px; display: grid; grid-template-columns: 245px minmax(400px, 1fr) 230px; min-height: calc(100vh - 150px); overflow: hidden; }.conversation-list { background: #fff; border-right: 1px solid #e2e8f0; }.conversation-list__header { align-items: center; border-bottom: 1px solid #edf1f7; display: flex; justify-content: space-between; padding: 20px 16px; }.conversation-list__header strong, .conversation-list__header small { display: block; }.conversation-list__header strong { color: #172554; font-size: 16px; }.conversation-list__header small { color: #94a3b8; font-size: 11px; margin-top: 3px; }.conversation-list__header button { background: #4f46e5; border: 0; border-radius: 7px; color: #fff; cursor: pointer; font-size: 20px; height: 30px; width: 30px; }.conversation-list__empty { color: #94a3b8; font-size: 12px; line-height: 1.8; padding: 42px 18px; text-align: center; }.conversation-item { background: transparent; border: 0; border-bottom: 1px solid #f1f5f9; cursor: pointer; display: block; padding: 14px 16px; text-align: left; width: 100%; }.conversation-item:hover, .conversation-item.active { background: #eef2ff; }.conversation-item strong, .conversation-item span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.conversation-item strong { color: #334155; font-size: 13px; }.conversation-item span { color: #94a3b8; font-size: 11px; margin-top: 5px; }.conversation-main { display: flex; flex-direction: column; min-width: 0; }.conversation-main__header { align-items: center; background: #fff; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; padding: 18px 24px; }.conversation-main__header h1 { color: #172554; font-size: 18px; margin: 0 0 4px; }.conversation-main__header p { color: #94a3b8; font-family: ui-monospace, monospace; font-size: 11px; margin: 0; }.conversation-state { background: #dcfce7; border-radius: 999px; color: #166534; font-size: 11px; padding: 5px 9px; }.conversation-messages { flex: 1; min-height: 420px; overflow: auto; padding: 28px 30px; }.conversation-empty { color: #94a3b8; padding: 100px 20px; text-align: center; }.conversation-empty__icon { color: #6366f1; font-size: 34px; }.conversation-empty h2 { color: #334155; font-size: 18px; margin: 10px 0 7px; }.conversation-empty p { font-size: 13px; margin: 0; }.message { margin: 0 auto 22px; max-width: 760px; }.message__role { color: #64748b; font-size: 11px; font-weight: 800; margin-bottom: 6px; }.message__body { border-radius: 10px; color: #334155; line-height: 1.75; padding: 13px 16px; white-space: pre-wrap; }.message--user .message__body { background: #e0e7ff; border: 1px solid #c7d2fe; }.message--assistant .message__body { background: #fff; border: 1px solid #e2e8f0; }.conversation-input { background: #fff; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; padding: 16px 22px; }.conversation-input textarea { border: 1px solid #cbd5e1; border-radius: 8px; flex: 1; font: inherit; line-height: 1.5; padding: 10px 12px; resize: none; }.conversation-input textarea:focus { border-color: #6366f1; outline: 0; }.conversation-input button { align-self: flex-end; background: #4338ca; border: 0; border-radius: 8px; color: #fff; cursor: pointer; font-weight: 700; padding: 11px 18px; }.conversation-input button:disabled { cursor: not-allowed; opacity: .55; }.conversation-error { background: #fef2f2; color: #b91c1c; font-size: 12px; margin: 0 22px 10px; padding: 8px 12px; }.conversation-inspector { background: #f8fafc; border-left: 1px solid #e2e8f0; padding: 22px 16px; }.conversation-inspector h2 { color: #172554; font-size: 15px; margin: 0 0 4px; }.inspector-subtitle { color: #94a3b8; font-size: 11px; line-height: 1.5; margin: 0 0 18px; }.inspector-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 10px; padding: 12px; }.inspector-card span, .inspector-card small { color: #94a3b8; display: block; font-size: 10px; }.inspector-card strong, .inspector-card code { color: #334155; display: block; font-size: 12px; margin: 5px 0; overflow-wrap: anywhere; }.inspector-card code { color: #4f46e5; font-family: ui-monospace, monospace; }.inspector-hint { color: #64748b; font-size: 11px; line-height: 1.6; margin-top: 18px; }
@media (max-width: 1050px) { .conversation-page { grid-template-columns: 210px minmax(320px, 1fr); }.conversation-inspector { display: none; } }
@media (max-width: 700px) { .conversation-page { display: block; }.conversation-list { border-bottom: 1px solid #e2e8f0; border-right: 0; max-height: 240px; overflow: auto; }.conversation-main { min-height: 620px; } }
</style>
