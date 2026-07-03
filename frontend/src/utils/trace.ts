const STORAGE_KEY = 'ioc_trace_id'

let _traceId = sessionStorage.getItem(STORAGE_KEY) || ''

export function getTraceId(): string {
  if (!_traceId) {
    _traceId = `trace_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
    sessionStorage.setItem(STORAGE_KEY, _traceId)
  }
  return _traceId
}

export function setTraceId(id: string): void {
  _traceId = id
  sessionStorage.setItem(STORAGE_KEY, id)
}

export function resetTraceId(): void {
  _traceId = ''
  sessionStorage.removeItem(STORAGE_KEY)
}
