<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { marked } from 'marked'

import {
  createReportChatSession,
  getReportChatMessages,
  sendReportChatMessage,
  type ReportChatMessage,
  type ReportQuestionScope,
  type RagSource,
} from '@/api/reportChat'

const props = withDefaults(defineProps<{
  reportId?: number | null
  reportTitle?: string | null
  userId?: string
  compact?: boolean
}>(), {
  reportId: null,
  reportTitle: '',
  userId: 'anonymous',
  compact: false,
})

const quickQuestions = [
  '为什么判断为高风险？',
  '这个风险为什么排第一？',
  '主要异常项是什么？',
  '异常清单中哪个最严重？',
  '建议动作应该先做哪一个？',
  '这个结论依据哪些数据？',
]

const messages = ref<ReportChatMessage[]>([])
const input = ref('')
const sessionId = ref('')
const activeReportId = ref<number | null>(null)
const loadingSession = ref(false)
const sending = ref(false)
const error = ref('')
const lastTraceId = ref('')
const messageListRef = ref<HTMLElement | null>(null)

const canSend = computed(() => Boolean(props.reportId && sessionId.value && input.value.trim() && !sending.value))
const panelTitle = computed(() => props.reportTitle || '本质安全分析报告')

watch(
  () => props.reportId,
  (reportId) => {
    void prepareSession(reportId ?? null)
  },
  { immediate: true },
)

async function prepareSession(reportId: number | null) {
  error.value = ''
  lastTraceId.value = ''
  input.value = ''
  messages.value = []
  sessionId.value = ''
  activeReportId.value = reportId

  if (!reportId) {
    return
  }

  loadingSession.value = true
  try {
    const session = await createReportChatSession(reportId, props.userId)
    if (activeReportId.value !== reportId) {
      return
    }
    sessionId.value = session.session_id
    const history = await getReportChatMessages(session.session_id)
    if (activeReportId.value === reportId) {
      messages.value = history.messages
      await scrollToBottom()
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建报告追问会话失败'
  } finally {
    if (activeReportId.value === reportId) {
      loadingSession.value = false
    }
  }
}

async function sendCurrentMessage() {
  const question = input.value.trim()
  if (!props.reportId || !sessionId.value || !question || sending.value) {
    return
  }

  const now = new Date().toISOString()
  messages.value.push({
    role: 'user',
    content: question,
    evidence_refs: [],
    question_scope: null,
    created_at: now,
    used_rag: false,
    rag_source_refs: [],
    rag_sources: [],
  })
  input.value = ''
  sending.value = true
  error.value = ''
  await scrollToBottom()

  try {
    const response = await sendReportChatMessage({
      sessionId: sessionId.value,
      reportId: props.reportId,
      question,
    })
    lastTraceId.value = response.trace_id
    messages.value.push({
      role: 'assistant',
      content: response.answer,
      evidence_refs: response.evidence_refs,
      question_scope: response.question_scope,
      created_at: new Date().toISOString(),
      used_rag: response.used_rag,
      rag_source_refs: response.rag_source_refs,
      rag_sources: response.rag_sources,
    })
    await scrollToBottom()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '发送追问失败'
  } finally {
    sending.value = false
  }
}

function askQuickQuestion(question: string) {
  if (sending.value || loadingSession.value) {
    return
  }
  input.value = question
  void sendCurrentMessage()
}

function renderAssistantMarkdown(text: string): string {
  return marked.parse(text.replace(/</g, '&lt;'), { async: false, gfm: true }) as string
}

function scopeLabel(scope: ReportQuestionScope | null): string {
  const labels: Record<ReportQuestionScope, string> = {
    report_internal: '报告内',
    report_related: '报告扩展',
    ioc_global: '全局问题',
    out_of_scope: '越界问题',
  }
  return scope ? labels[scope] : ''
}

function knowledgeSources(message: ReportChatMessage): RagSource[] {
  if (message.rag_sources?.length) {
    return message.rag_sources
  }
  return (message.rag_source_refs || []).map((ref) => ({
    source_id: ref,
    document_title: ref,
  }))
}

function sourceMeta(source: RagSource): string {
  const metadata = source.metadata || {}
  const parts = [
    metadata.source,
    metadata.doc_type,
    metadata.version ? `v${metadata.version}` : '',
  ]
    .filter((item): item is string => typeof item === 'string' && item.length > 0)
  return parts.join(' / ')
}

function sourceSnippet(source: RagSource): string {
  const text = source.content || ''
  return text.length > 86 ? `${text.slice(0, 86)}...` : text
}

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}
</script>

<template>
  <section class="report-chat" :class="{ 'report-chat--compact': compact }">
    <header class="report-chat__header">
      <div>
        <h2>AI 深度解答</h2>
        <p>{{ panelTitle }}</p>
      </div>
      <span class="report-chat__badge">深度解答</span>
    </header>

    <div v-if="!reportId" class="report-chat__empty">
      请选择一份分析报告后开始追问。
    </div>

    <template v-else>
      <div class="report-chat__notice">
        当前会话基于本报告回答，支持原因解释、异常下钻、风险排序依据和建议动作追问。
      </div>

      <div class="quick-questions" aria-label="快捷问题">
        <button
          v-for="question in quickQuestions"
          :key="question"
          type="button"
          :disabled="loadingSession || sending"
          @click="askQuickQuestion(question)"
        >
          {{ question }}
        </button>
      </div>

      <div ref="messageListRef" class="report-chat__messages">
        <div v-if="loadingSession" class="report-chat__state">正在创建报告会话...</div>
        <div v-else-if="messages.length === 0" class="report-chat__state">
          可以直接输入问题，也可以点击上方快捷问题开始。
        </div>

        <article
          v-for="(message, index) in messages"
          :key="`${message.role}-${index}-${message.created_at}`"
          class="chat-message"
          :class="message.role === 'user' ? 'chat-message--user' : 'chat-message--assistant'"
        >
          <div class="chat-message__meta">
            <strong>{{ message.role === 'user' ? '你' : 'AI' }}</strong>
            <span v-if="scopeLabel(message.question_scope)">{{ scopeLabel(message.question_scope) }}</span>
          </div>
          <div
            v-if="message.role === 'assistant'"
            class="chat-message__bubble markdown-content"
            v-html="renderAssistantMarkdown(message.content)"
          />
          <div v-else class="chat-message__bubble">{{ message.content }}</div>
          <div v-if="message.evidence_refs.length" class="evidence-refs">
            <span>报告依据</span>
            <code v-for="ref in message.evidence_refs" :key="ref">{{ ref }}</code>
          </div>
          <div v-if="message.used_rag && knowledgeSources(message).length" class="knowledge-sources">
            <span class="knowledge-sources__label">知识库依据</span>
            <div
              v-for="source in knowledgeSources(message)"
              :key="source.source_id"
              class="knowledge-source"
            >
              <div class="knowledge-source__title">
                {{ source.document_title || source.source_id }}
                <code>{{ source.source_id }}</code>
              </div>
              <div v-if="sourceMeta(source)" class="knowledge-source__meta">{{ sourceMeta(source) }}</div>
              <div v-if="sourceSnippet(source)" class="knowledge-source__snippet">{{ sourceSnippet(source) }}</div>
            </div>
          </div>
        </article>

        <div v-if="sending" class="report-chat__state">AI 正在基于报告生成回答...</div>
      </div>

      <p v-if="error" class="report-chat__error">{{ error }}</p>

      <form class="report-chat__input-area" @submit.prevent="sendCurrentMessage">
        <textarea
          v-model="input"
          class="report-chat__input"
          rows="2"
          placeholder="围绕当前报告继续追问..."
          :disabled="loadingSession || sending"
          @keydown.enter.exact.prevent="sendCurrentMessage"
        />
        <button type="submit" class="report-chat__send" :disabled="!canSend">
          {{ sending ? '发送中' : '发送' }}
        </button>
      </form>

      <div v-if="sessionId || lastTraceId" class="report-chat__debug">
        <span v-if="sessionId">Session: <code>{{ sessionId }}</code></span>
        <span v-if="lastTraceId">Trace: <code>{{ lastTraceId }}</code></span>
      </div>
    </template>
  </section>
</template>

<style scoped>
.report-chat {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  min-height: 620px;
  overflow: hidden;
}

.report-chat--compact {
  min-height: 100%;
}

.report-chat__header {
  align-items: flex-start;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 16px 18px;
}

.report-chat__header h2 {
  color: var(--color-heading);
  font-size: 18px;
  margin: 0 0 4px;
}

.report-chat__header p {
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}

.report-chat__badge {
  background: #eef2ff;
  border-radius: 4px;
  color: #3730a3;
  flex: 0 0 auto;
  font-size: 11px;
  font-weight: 800;
  padding: 3px 8px;
  text-transform: uppercase;
}

.report-chat__notice {
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.6;
  padding: 10px 18px;
}

.quick-questions {
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 18px;
}

.quick-questions button {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: #475569;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  padding: 6px 10px;
}

.quick-questions button:hover:not(:disabled) {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #3730a3;
}

.quick-questions button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.report-chat__messages {
  flex: 1;
  min-height: 260px;
  overflow-y: auto;
  padding: 16px 18px;
}

.report-chat__state,
.report-chat__empty {
  color: var(--color-text-muted);
  font-size: 14px;
  line-height: 1.7;
  padding: 40px 16px;
  text-align: center;
}

.chat-message {
  margin-bottom: 16px;
}

.chat-message__meta {
  align-items: center;
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.chat-message__meta strong {
  font-size: 12px;
}

.chat-message__meta span {
  background: #f1f5f9;
  border-radius: 4px;
  color: var(--color-text-muted);
  font-size: 11px;
  font-weight: 800;
  padding: 2px 6px;
}

.chat-message--user .chat-message__meta strong {
  color: #3730a3;
}

.chat-message--assistant .chat-message__meta strong {
  color: #166534;
}

.chat-message__bubble {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  color: var(--color-text);
  font-size: 14px;
  line-height: 1.7;
  padding: 10px 12px;
  white-space: pre-wrap;
}

.chat-message--user .chat-message__bubble {
  background: #eef2ff;
  border-color: #c7d2fe;
}

.evidence-refs {
  align-items: center;
  color: var(--color-text-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 6px;
  margin-top: 8px;
}

.knowledge-sources {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.knowledge-sources__label {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.knowledge-source {
  background: #f8fafc;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  display: grid;
  gap: 4px;
  padding: 8px 10px;
}

.knowledge-source__title {
  align-items: center;
  color: #1e3a8a;
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  font-weight: 800;
  gap: 6px;
  line-height: 1.5;
}

.knowledge-source__meta,
.knowledge-source__snippet {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.evidence-refs code,
.knowledge-source code,
.report-chat__debug code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  padding: 1px 6px;
}

.report-chat__error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #b91c1c;
  font-size: 13px;
  margin: 0 18px 12px;
  padding: 8px 12px;
}

.report-chat__input-area {
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: 10px;
  padding: 12px 18px;
}

.report-chat__input {
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  flex: 1;
  min-width: 0;
  padding: 10px 12px;
  resize: none;
}

.report-chat__input:focus {
  border-color: #6366f1;
  outline: none;
}

.report-chat__send {
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
  min-height: 42px;
  padding: 0 18px;
  white-space: nowrap;
}

.report-chat__send:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.report-chat__debug {
  border-top: 1px solid #e2e8f0;
  color: var(--color-text-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 12px;
  padding: 8px 18px;
}

.markdown-content :deep(h3) {
  color: var(--color-heading);
  font-size: 15px;
  margin: 10px 0 6px;
}

.markdown-content :deep(p) {
  margin: 6px 0;
}

.markdown-content :deep(ol),
.markdown-content :deep(ul) {
  margin: 6px 0;
  padding-left: 20px;
}

.markdown-content :deep(li) {
  margin: 3px 0;
}

@media (max-width: 720px) {
  .report-chat__input-area {
    flex-direction: column;
  }

  .report-chat__send {
    width: 100%;
  }
}
</style>
