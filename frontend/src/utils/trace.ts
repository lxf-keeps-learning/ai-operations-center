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
