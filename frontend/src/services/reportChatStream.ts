import { buildApiUrl } from '@/utils/request'
import { createTraceId, setLastTraceId } from '@/utils/trace'
import type {
  ReportQuestionScope,
  RagSource,
} from '@/api/reportChat'

export interface ReportChatStreamCompleted {
  trace_id: string
  conversation_id: string
  session_id: string
  runtime_session_id: string
  message_id: string
  question_scope: ReportQuestionScope
  answer: string
  answer_type: 'normal' | 'insufficient_evidence' | 'boundary'
  evidence_refs: string[]
  query_scope: Record<string, unknown>
  used_rag: boolean
  rag_source_refs: string[]
  rag_sources: RagSource[]
  errors: Record<string, unknown>[]
}

interface StreamHandlers {
  onStarted: (traceId: string) => void
  onDelta: (delta: string) => void
  onReset: () => void
  onCompleted: (event: ReportChatStreamCompleted) => void
  onError: (error: Error) => void
  onClose: () => void
}

export interface ReportChatStreamController {
  abort: () => void
}

interface SseBlock {
  eventType: string
  data: string
}

const STREAM_OVERALL_TIMEOUT_MS = 125_000
const STREAM_IDLE_TIMEOUT_MS = 35_000

export function streamReportChatMessage(
  params: { sessionId: string; reportId: number; question: string },
  handlers: StreamHandlers,
): ReportChatStreamController {
  const controller = new AbortController()
  const traceId = createTraceId()

  let overallTimer: number | undefined
  let idleTimer: number | undefined
  let settled = false

  const clearTimers = () => {
    if (overallTimer !== undefined) window.clearTimeout(overallTimer)
    if (idleTimer !== undefined) window.clearTimeout(idleTimer)
    overallTimer = undefined
    idleTimer = undefined
  }

  const fail = (message: string, code: string) => {
    if (settled) return
    settled = true
    clearTimers()
    controller.abort()
    const error = new Error(message)
    ;(error as Error & { code?: string }).code = code
    handlers.onError(error)
  }

  const armIdleTimer = () => {
    if (idleTimer !== undefined) window.clearTimeout(idleTimer)
    idleTimer = window.setTimeout(() => {
      fail('事件流空闲超时，已断开连接', 'STREAM_IDLE_TIMEOUT')
    }, STREAM_IDLE_TIMEOUT_MS)
  }

  overallTimer = window.setTimeout(() => {
    fail('回答生成超过时限（125 秒），已停止等待', 'STREAM_TIMEOUT')
  }, STREAM_OVERALL_TIMEOUT_MS)

  fetch(buildApiUrl(`/chat/sessions/${params.sessionId}/messages/stream`), {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      'X-Trace-Id': traceId,
    },
    body: JSON.stringify({
      report_id: params.reportId,
      question: params.question,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      const responseTraceId = response.headers.get('X-Trace-Id') || traceId
      setLastTraceId(responseTraceId)

      if (!response.ok) {
        const message = await readErrorMessage(response)
        fail(message, 'STREAM_HTTP_ERROR')
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        fail('流式响应不可读取', 'STREAM_READ_ERROR')
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
          armIdleTimer() // 任意业务事件或心跳刷新空闲计时
          try {
            dispatchStreamEvent(block.eventType, JSON.parse(block.data), handlers)
          } catch {
            fail(`无法解析流式回答事件：${block.data.slice(0, 100)}`, 'STREAM_PARSE_ERROR')
          }
        }
      }

      try {
        armIdleTimer()
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          consume()
        }
        buffer += decoder.decode()
        if (buffer.trim()) consume(true)
        if (!settled) {
          settled = true
          clearTimers()
          handlers.onClose()
        }
      } catch (error) {
        if (isAbortError(error)) {
          if (!settled) clearTimers() // 用户主动取消：静默收尾
          return
        }
        fail(error instanceof Error ? error.message : String(error), 'STREAM_READ_ERROR')
      }
    })
    .catch((error) => {
      if (isAbortError(error)) {
        if (!settled) clearTimers()
        return
      }
      fail(error instanceof Error ? error.message : String(error), 'STREAM_NETWORK_ERROR')
    })

  return {
    abort: () => {
      settled = true
      clearTimers()
      controller.abort()
    },
  }
}

function dispatchStreamEvent(
  eventType: string,
  payload: Record<string, unknown>,
  handlers: StreamHandlers,
) {
  switch (eventType) {
    case 'message_started':
      handlers.onStarted(String(payload.trace_id || ''))
      break
    case 'answer_delta':
      handlers.onDelta(String(payload.delta || ''))
      break
    case 'answer_reset':
      handlers.onReset()
      break
    case 'message_completed':
      handlers.onCompleted(payload as unknown as ReportChatStreamCompleted)
      break
    case 'message_failed':
      handlers.onError(new Error(String(payload.error_message || payload.message || 'AI 深度解答生成失败')))
      break
    case 'stream_closed':
      break
  }
}

function parseSseBlock(block: string): SseBlock | null {
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

async function readErrorMessage(response: Response): Promise<string> {
  const text = await response.text().catch(() => '')
  if (!text) return `HTTP ${response.status}`
  try {
    const payload = JSON.parse(text) as { message?: string; detail?: string }
    return payload.message || payload.detail || `HTTP ${response.status}`
  } catch {
    return `HTTP ${response.status}: ${text.slice(0, 160)}`
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}
