export interface ApiResponse<T> {
  code: number
  message: string
  traceId: string
  success: boolean
  data: T
}
