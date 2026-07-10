<script setup lang="ts">
import { ref } from 'vue'

import { streamRuntimeChat, type RuntimeChatStreamCompleted } from '@/api/runtime'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const props = withDefaults(defineProps<{
  promptCode?: string
}>(), {
  promptCode: undefined,
})

const messages = ref<ChatMessage[]>([])
const input = ref('')
const loading = ref(false)
const error = ref('')
const streaming = ref(false)
const conversationId = ref<string | null>(null)
const lastSessionId = ref<string | null>(null)
const lastTraceId = ref<string | null>(null)

function sendMessage() {
  const text = input.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  streaming.value = true
  error.value = ''

  const assistantMsg: ChatMessage = { role: 'assistant', content: '' }
  messages.value.push(assistantMsg)

  const stream = streamRuntimeChat(
    { message: text, conversation_id: conversationId.value, prompt_code: props.promptCode },
    {
      onStarted() {},
      onDelta(delta: string) {
        assistantMsg.content += delta
      },
      onCompleted(event: RuntimeChatStreamCompleted) {
        conversationId.value = event.conversation_id
        lastSessionId.value = event.session_id
        lastTraceId.value = event.trace_id
        assistantMsg.content = event.answer
      },
      onError(e: Error) {
        error.value = e.message
      },
      onClose() {
        loading.value = false
        streaming.value = false
      },
    },
  )

  // 如果需要在组件卸载时取消，可保存 stream
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-panel__header">
      <h2>AI 对话</h2>
      <span class="chat-panel__badge">Runtime Chat</span>
    </div>

    <div class="chat-panel__messages">
      <div v-if="messages.length === 0 && !loading" class="chat-panel__empty">
        输入消息开始与 AI 对话
      </div>
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="chat-message"
        :class="msg.role === 'user' ? 'chat-message--user' : 'chat-message--assistant'"
      >
        <div class="chat-message__role">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
        <div
          class="chat-message__bubble"
          :class="{ 'chat-message__bubble--streaming': streaming && i === messages.length - 1 && msg.role === 'assistant' }"
        >{{ msg.content }}</div>
      </div>
      <div v-if="loading && messages.length === 0" class="chat-panel__loading">AI 思考中...</div>
    </div>

    <p v-if="error" class="chat-panel__error">{{ error }}</p>

    <form class="chat-panel__input-area" @submit.prevent="sendMessage">
      <input
        v-model="input"
        class="chat-panel__input"
        placeholder="输入消息..."
        :disabled="loading"
      />
      <button
        class="chat-panel__send"
        type="submit"
        :disabled="loading || !input.trim()"
      >
        {{ loading ? '发送中' : '发送' }}
      </button>
    </form>

    <div v-if="lastSessionId || lastTraceId" class="chat-panel__debug">
      <span v-if="lastSessionId">Session: <code>{{ lastSessionId }}</code></span>
      <span v-if="lastTraceId">Trace: <code>{{ lastTraceId }}</code></span>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  height: 520px;
}

.chat-panel__header {
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: 12px;
  padding: 16px 20px;
}

.chat-panel__header h2 {
  color: var(--color-heading);
  font-size: 18px;
  margin: 0;
}

.chat-panel__badge {
  background: #f0fdf4;
  border-radius: 4px;
  color: #166534;
  font-size: 11px;
  font-weight: 800;
  padding: 2px 8px;
  text-transform: uppercase;
}

.chat-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.chat-panel__empty {
  color: var(--color-text-muted);
  font-size: 14px;
  padding: 60px 0;
  text-align: center;
}

.chat-panel__loading {
  color: var(--color-text-muted);
  font-size: 14px;
  padding: 10px 0;
  text-align: center;
}

.chat-message {
  margin-bottom: 16px;
}

.chat-message__role {
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.chat-message--user .chat-message__role {
  color: #6366f1;
}

.chat-message--assistant .chat-message__role {
  color: #166534;
}

.chat-message__bubble {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 15px;
  line-height: 1.7;
  padding: 12px 16px;
  white-space: pre-wrap;
}

.chat-message--user .chat-message__bubble {
  background: #eef2ff;
  border-color: #c7d2fe;
}

.chat-panel__error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #b91c1c;
  font-size: 13px;
  margin: 0 20px 12px;
  padding: 8px 12px;
}

.chat-panel__input-area {
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: 8px;
  padding: 12px 20px;
}

.chat-panel__input {
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  flex: 1;
  font-size: 15px;
  min-width: 0;
  padding: 10px 14px;
}

.chat-panel__input:focus {
  border-color: #6366f1;
  outline: none;
}

.chat-panel__send {
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
  padding: 0 20px;
  white-space: nowrap;
}

.chat-panel__send:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.chat-panel__debug {
  border-top: 1px solid #e2e8f0;
  color: var(--color-text-muted);
  display: flex;
  flex-wrap: wrap;
  font-size: 12px;
  gap: 16px;
  padding: 8px 20px;
}

.chat-panel__debug code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  padding: 1px 6px;
}

.chat-message__bubble--streaming::after {
  animation: blink 1s step-end infinite;
  color: #166534;
  content: '|';
  font-weight: 700;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
