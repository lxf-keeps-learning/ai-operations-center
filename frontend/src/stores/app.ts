import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getHealth } from '@/api/runtime'
import type { HealthStatus } from '@/types/api'

export const useAppStore = defineStore('app', () => {
  const health = ref<HealthStatus | null>(null)
  const loading = ref(false)
  const errorMessage = ref('')

  const apiStatus = computed(() => {
    if (loading.value) {
      return 'checking'
    }

    if (errorMessage.value) {
      return 'offline'
    }

    if (health.value?.status === 'UP') {
      return 'online'
    }

    return 'unknown'
  })

  async function checkHealth() {
    loading.value = true
    errorMessage.value = ''

    try {
      health.value = await getHealth()
    } catch (error) {
      health.value = null
      errorMessage.value = error instanceof Error ? error.message : '后端服务连接失败'
    } finally {
      loading.value = false
    }
  }

  return {
    health,
    loading,
    errorMessage,
    apiStatus,
    checkHealth,
  }
})
