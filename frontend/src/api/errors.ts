import { request } from '@/utils/request'
import type { ErrorCodeEntry } from '@/types/error-code'

export async function getErrorCodes() {
  return request<ErrorCodeEntry[]>('/errors/codes')
}
