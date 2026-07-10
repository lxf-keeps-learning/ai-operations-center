/**
 * Trace 工具 — 前端全链路追踪 ID 管理
 *
 * 每次 API 请求生成唯一 traceId，存入 sessionStorage 以便在页面刷新后仍可追溯。
 * 后端会通过 X-Trace-Id 请求头接收此 ID，并贯穿整个请求链路（API → Service → Graph → LLM）。
 *
 * 功能：
 *   createTraceId()     生成新 traceId（格式: trace_{timestamp}_{random}）
 *   getLastTraceId()    获取最近一次请求的 traceId
 *   setLastTraceId()    保存 traceId 到内存 + sessionStorage
 *   resetLastTraceId()  清除保存的 traceId
 */

const STORAGE_KEY = 'ioc_trace_id'

let _traceId = sessionStorage.getItem(STORAGE_KEY) || ''

export function createTraceId(): string {
  return `trace_${Date.now()}_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`
}

export function getLastTraceId(): string {
  return _traceId
}

export function setLastTraceId(id: string): void {
  _traceId = id
  sessionStorage.setItem(STORAGE_KEY, id)
}

export function resetLastTraceId(): void {
  _traceId = ''
  sessionStorage.removeItem(STORAGE_KEY)
}
