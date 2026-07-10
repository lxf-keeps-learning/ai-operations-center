import { buildApiUrl } from '@/utils/request'
import { createTraceId, setLastTraceId } from '@/utils/trace'
import type { OperationAnalyzeParams } from '@/api/operation'
import type { AnalysisStreamEvent, StreamController, StreamHandlers } from '@/types/analysisStream'

interface SseBlock {
  eventType: string
  data: string
}

export function streamOperationAnalysis(
  params: OperationAnalyzeParams,
  handlers: StreamHandlers,
): StreamController {
  const controller = new AbortController()
  const body = JSON.stringify(params)
  const traceId = createTraceId()

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
        handlers.onError(new Error(`HTTP ${response.status}: ${text}`))
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        handlers.onError(new Error('Response body is not readable'))
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

          try {
            handlers.onEvent(JSON.parse(parsed.data) as AnalysisStreamEvent)
          } catch {
            handlers.onError(new Error(`Failed to parse SSE data: ${parsed.data.slice(0, 100)}`))
          }
        }
      }

      try {
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
          return
        }
        handlers.onError(err instanceof Error ? err : new Error(String(err)))
        return
      }

      handlers.onClose()
    })
    .catch((err) => {
      if (err instanceof DOMException && err.name === 'AbortError') return
      handlers.onError(err instanceof Error ? err : new Error(String(err)))
    })

  return {
    abort: () => controller.abort(),
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
