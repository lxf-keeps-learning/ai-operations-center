import { request } from '@/utils/request'
import type { ModelProvider, RuntimeEnv } from '@/types/config'

export async function getModels() {
  return request<ModelProvider[]>('/config/models')
}

export async function getRuntime() {
  return request<RuntimeEnv>('/config/runtime')
}
