import { buildApiUrl } from '@/utils/request'
import { createTraceId, setLastTraceId } from '@/utils/trace'
import type { OperationAnalyzeParams } from '@/api/operation'
import type { AnalysisStreamEvent, StreamController, StreamHandlers } from '@/types/analysisStream'

interface SseBlock {
  eventType: string
  data: string
}

const STREAM_OVERALL_TIMEOUT_MS = 125_000
const STREAM_IDLE_TIMEOUT_MS = 35_000

export function streamOperationAnalysis(
  params: OperationAnalyzeParams,
  handlers: StreamHandlers,
): StreamController {
  const controller = new AbortController()
  const body = JSON.stringify(params)
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
    fail('报告生成超过时限（125 秒），已停止等待', 'STREAM_TIMEOUT')
  }, STREAM_OVERALL_TIMEOUT_MS)

  fetch(buildApiUrl('/operation/analyze/stream'), {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      'X-Trace-Id': traceId,
    },
    body,
    signal: controller.signal,
  })
    .then(async (response) => {
      setLastTraceId(response.headers.get('X-Trace-Id') || traceId)
      if (!response.ok) {
        const text = await response.text().catch(() => '')
        fail(`HTTP ${response.status}: ${text}`, 'STREAM_HTTP_ERROR')
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        fail('Response body is not readable', 'STREAM_READ_ERROR')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      const consumeBuffer = (flush = false) => {
        const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
        const blocks = normalized.split(/\n\n+/)
        buffer = flush ? '' : (blocks.pop() || '')

        const completeBlocks = flush ? blocks.filter(Boolean) : blocks
        for (const rawBlock of completeBlocks) {
          const parsed = parseSseBlock(rawBlock)
          if (!parsed) continue

          armIdleTimer() // 任意业务事件或心跳刷新空闲计时
          try {
            handlers.onEvent(JSON.parse(parsed.data) as AnalysisStreamEvent)
          } catch {
            fail(`Failed to parse SSE data: ${parsed.data.slice(0, 100)}`, 'STREAM_PARSE_ERROR')
          }
        }
      }

      try {
        armIdleTimer()
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          consumeBuffer()
        }

        buffer += decoder.decode()
        if (buffer.trim()) {
          consumeBuffer(true)
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          if (!settled) clearTimers() // 用户主动取消：静默收尾
          return
        }
        fail(err instanceof Error ? err.message : String(err), 'STREAM_READ_ERROR')
        return
      }

      if (!settled) {
        settled = true
        clearTimers()
        handlers.onClose()
      }
    })
    .catch((err) => {
      if (err instanceof DOMException && err.name === 'AbortError') {
        if (!settled) clearTimers()
        return
      }
      fail(err instanceof Error ? err.message : String(err), 'STREAM_NETWORK_ERROR')
    })

  return {
    abort: () => {
      settled = true
      clearTimers()
      controller.abort()
    },
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

    if (field === 'event') {
      eventType = value.trim()
    } else if (field === 'data') {
      dataLines.push(value)
    }
  }

  if (!eventType || dataLines.length === 0) return null
  return { eventType, data: dataLines.join('\n') }
}
