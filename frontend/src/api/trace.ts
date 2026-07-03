import { request } from '@/utils/request'

export interface RuntimeTraceSpan {
  id: string
  trace_id: string
  span_id: string | null
  parent_span_id: string | null
  conversation_id: string | null
  session_id: string
  span_type: string
  graph_name: string | null
  node_name: string | null
  tool_name: string | null
  model_name: string | null
  prompt_id: string | null
  prompt_code: string | null
  prompt_version: number | null
  prompt_snapshot: string | null
  input_data: Record<string, unknown> | null
  output_data: Record<string, unknown> | null
  cost_ms: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  status: string
  error_code: string | null
  error_message: string | null
  created_at: string
}

export interface Span {
  spanId: string
  parentSpanId: string
  operation: string
  startTime: string
  endTime: string
  status: string
  service: string
  metadata?: Record<string, unknown>
}

export interface TraceData {
  traceId: string
  spans: Span[]
}

export async function getTrace(traceId: string) {
  const spans = await request<RuntimeTraceSpan[]>(`/runtime/traces/${traceId}`)
  return {
    traceId,
    spans: spans.map(toTimelineSpan),
  }
}

function toTimelineSpan(span: RuntimeTraceSpan): Span {
  return {
    spanId: span.span_id || span.id,
    parentSpanId: span.parent_span_id || '',
    operation: buildOperationName(span),
    startTime: span.created_at,
    endTime: span.created_at,
    status: span.status,
    service: span.span_type,
    metadata: {
      conversationId: span.conversation_id,
      sessionId: span.session_id,
      graphName: span.graph_name,
      nodeName: span.node_name,
      toolName: span.tool_name,
      modelName: span.model_name,
      promptId: span.prompt_id,
      promptCode: span.prompt_code,
      promptVersion: span.prompt_version,
      promptSnapshot: span.prompt_snapshot,
      costMs: span.cost_ms,
      tokens: {
        prompt: span.prompt_tokens,
        completion: span.completion_tokens,
        total: span.total_tokens,
      },
      input: span.input_data,
      output: span.output_data,
      error: span.error_message
        ? {
            code: span.error_code,
            message: span.error_message,
          }
        : null,
    },
  }
}

function buildOperationName(span: RuntimeTraceSpan) {
  if (span.graph_name) return span.graph_name
  if (span.node_name) return span.node_name
  if (span.tool_name) return span.tool_name
  if (span.model_name) return span.model_name
  const event = span.output_data?.event || span.input_data?.event
  return typeof event === 'string' ? event : span.span_type
}
