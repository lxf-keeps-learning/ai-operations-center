import { request } from '@/utils/request'

export interface HealthData {
  status: string
  env: string
  version: string
  database: string
  redis: string
  llm: string
}

export async function getHealth() {
  return request<HealthData>('/health')
}
