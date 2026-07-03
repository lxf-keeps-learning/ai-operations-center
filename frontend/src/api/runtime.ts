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
