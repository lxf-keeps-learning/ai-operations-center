import { request } from '@/utils/request'
import type { ModelProvider, RuntimeEnv } from '@/types/config'

export async function getModels() {
  return request<ModelProvider[]>('/config/models')
}

export async function getRuntime() {
  return request<RuntimeEnv>('/config/runtime')
}

export async function selectModel(provider: string, model: string) {
  return request<ModelProvider>('/config/models/selection', {
    method: 'PUT',
    body: JSON.stringify({ provider, model }),
  })
}
