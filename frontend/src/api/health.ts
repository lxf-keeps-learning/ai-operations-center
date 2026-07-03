import { request } from '@/utils/request'

export interface HealthData {
  status: string
  database: string
  redis: string
  llm: string
}

export async function getHealth() {
  return request<HealthData>('/health')
}
