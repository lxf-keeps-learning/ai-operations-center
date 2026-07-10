import type {
  AgentChatRequest,
  AgentAnalyzeRequest,
  AgentTaskResponse,
  ConversationSummary,
  FeedbackRequest,
  FeedbackResponse,
  HealthStatus,
  ItemCreateRequest,
  ItemResponse,
  PaginatedResult,
  StreamEventName,
  StreamEventPayload,
} from '@/types/api'
import { buildApiUrl, request } from '@/utils/request'

interface StreamHandlers {
  onEvent?: (event: StreamEventPayload) => void
  onError?: (error: Error) => void
}

export interface AgentStreamController {
  source: EventSource
  close: () => void
}

export interface RuntimeChatStreamCompleted {
  conversation_id: string
  session_id: string
  trace_id: string
  answer: string
}

interface RuntimeChatStreamHandlers {
  onStarted: (traceId: string) => void
  onDelta: (delta: string) => void
  onCompleted: (event: RuntimeChatStreamCompleted) => void
  onError: (error: Error) => void
  onClose: () => void
}

export interface RuntimeChatStreamController {
  abort: () => void
}

const streamEvents: StreamEventName[] = ['start', 'progress', 'token', 'data', 'error', 'done', 'stop']

export async function getHealth() {
  return request<HealthStatus>('/health')
}

export async function analyzeAgent(payload: AgentAnalyzeRequest) {
  return request<AgentTaskResponse>('/agent/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function chatAgent(payload: AgentChatRequest) {
  return request<AgentTaskResponse>('/agent/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listConversations(params: { agent_code?: string; page?: number; page_size?: number } = {}) {
  const query = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      query.set(key, String(value))
    }
  })

  const path = query.toString() ? `/conversations?${query}` : '/conversations'
  return request<PaginatedResult<ConversationSummary>>(path)
}

export async function submitFeedback(payload: FeedbackRequest) {
  return request<FeedbackResponse>('/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createAgentStream(
  params: { traceId: string; sessionId?: string },
  handlers: StreamHandlers = {},
): AgentStreamController {
  const source = new EventSource(buildApiUrl('/agent/stream', params))

  streamEvents.forEach((eventName) => {
    source.addEventListener(eventName, (message) => {
      const event = parseStreamEvent(eventName, message as MessageEvent<string>)
      handlers.onEvent?.(event)

      if (eventName === 'error') {
        handlers.onError?.(new Error(event.message || 'SSE 返回错误事件'))
      }
    })
  })

  source.onerror = () => {
    handlers.onError?.(new Error('SSE 连接异常或已断开'))
  }

  return {
    source,
    close: () => source.close(),
  }
}

export async function listItems(params: { page?: number; page_size?: number; is_active?: boolean } = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      query.set(key, String(value))
    }
  })
  const path = query.toString() ? `/items?${query}` : '/items'
  return request<PaginatedResult<ItemResponse>>(path)
}

export async function createItem(payload: ItemCreateRequest) {
  return request<ItemResponse>('/items', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteItem(id: number) {
  return request<boolean>(`/items/${id}`, {
    method: 'DELETE',
  })
}

export function streamRuntimeChat(
  params: {
    message: string
    conversation_id?: string | null
    user_id?: string
    prompt_code?: string | null
  },
  handlers: RuntimeChatStreamHandlers,
): RuntimeChatStreamController {
  const controller = new AbortController()

  fetch(buildApiUrl('/runtime/chat/stream'), {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message: params.message,
      conversation_id: params.conversation_id || null,
      user_id: params.user_id || 'anonymous',
      prompt_code: params.prompt_code || null,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text().catch(() => '')
        handlers.onError(new Error(text || `HTTP ${response.status}`))
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        handlers.onError(new Error('流式响应不可读取'))
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      const consume = (flush = false) => {
        const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
        const blocks = normalized.split(/\n\n+/)
        buffer = flush ? '' : (blocks.pop() || '')
        for (const rawBlock of flush ? blocks.filter(Boolean) : blocks) {
          const block = parseSseBlock(rawBlock)
          if (!block) continue
          dispatchRuntimeStreamEvent(block.eventType, block.data, handlers)
        }
      }

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          consume()
        }
        buffer += decoder.decode()
        if (buffer.trim()) consume(true)
        handlers.onClose()
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        handlers.onError(error instanceof Error ? error : new Error(String(error)))
      }
    })
    .catch((error) => {
      if (error instanceof DOMException && error.name === 'AbortError') return
      handlers.onError(error instanceof Error ? error : new Error(String(error)))
    })

  return { abort: () => controller.abort() }
}

function parseSseBlock(block: string): { eventType: string; data: string } | null {
  let eventType = ''
  const dataLines: string[] = []
  for (const rawLine of block.split('\n')) {
    const line = rawLine.trimEnd()
    if (!line || line.startsWith(':')) continue
    const separatorIndex = line.indexOf(':')
    const field = separatorIndex >= 0 ? line.slice(0, separatorIndex) : line
    const rawValue = separatorIndex >= 0 ? line.slice(separatorIndex + 1) : ''
    const value = rawValue.startsWith(' ') ? rawValue.slice(1) : rawValue
    if (field === 'event') eventType = value.trim()
    if (field === 'data') dataLines.push(value)
  }
  return eventType && dataLines.length
    ? { eventType, data: dataLines.join('\n') }
    : null
}

function dispatchRuntimeStreamEvent(
  eventType: string,
  data: string,
  handlers: RuntimeChatStreamHandlers,
) {
  let payload: Record<string, unknown>
  try {
    payload = JSON.parse(data) as Record<string, unknown>
  } catch {
    return
  }

  switch (eventType) {
    case 'message_started':
      handlers.onStarted(String(payload.trace_id || ''))
      break
    case 'token':
      handlers.onDelta(String(payload.delta || ''))
      break
    case 'message_completed':
      handlers.onCompleted(payload as unknown as RuntimeChatStreamCompleted)
      break
    case 'message_failed':
      handlers.onError(new Error(String(payload.error_message || 'AI 回复生成失败')))
      break
    case 'stream_closed':
      break
  }
}

function parseStreamEvent(event: StreamEventName, message: MessageEvent<string>): StreamEventPayload {
  if (!message.data) {
    return { event }
  }

  try {
    return {
      event,
      ...(JSON.parse(message.data) as Record<string, unknown>),
    }
  } catch {
    return {
      event,
      message: message.data,
    }
  }
}
