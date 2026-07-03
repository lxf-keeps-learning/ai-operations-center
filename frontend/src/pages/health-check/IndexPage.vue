<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getHealth, type HealthData } from '@/api/health'
import StatusCard from '@/components/status-card/StatusCard.vue'

const health = ref<HealthData | null>(null)
const loading = ref(true)
const error = ref('')

async function fetch() {
  loading.value = true
  error.value = ''
  try {
    health.value = await getHealth()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '请求失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetch)
</script>

<template>
  <div class="health-check">
    <h1>健康检查</h1>
    <p class="page-subtitle">后端服务运行状态</p>

    <div v-if="loading" class="page-loading">检测中...</div>
    <p v-else-if="error" class="page-error">{{ error }}</p>

    <section v-if="health" class="health-grid">
      <StatusCard
        label="服务状态"
        :value="health.status"
        :tone="health.status === 'UP' ? 'success' : 'danger'"
      />
      <StatusCard
        label="数据库"
        :value="health.database"
        :tone="health.database === 'MOCK' ? 'warning' : 'success'"
      />
      <StatusCard
        label="Redis"
        :value="health.redis"
        :tone="health.redis === 'DISABLED' ? 'info' : health.redis === 'UP' ? 'success' : 'danger'"
      />
      <StatusCard
        label="大模型"
        :value="health.llm"
        :tone="health.llm === 'MOCK' ? 'warning' : 'success'"
      />
    </section>

    <button v-if="!loading" class="refresh-btn" @click="fetch">刷新检测</button>
  </div>
</template>

<style scoped>
h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0 0 4px;
}

.page-subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0 0 24px;
}

.page-loading,
.page-error {
  font-size: 15px;
  margin-bottom: 20px;
}

.page-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  padding: 12px 16px;
}

.health-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  margin-bottom: 24px;
}

.refresh-btn {
  align-items: center;
  background: #0f172a;
  border: none;
  border-radius: 8px;
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  font-size: 15px;
  font-weight: 800;
  justify-content: center;
  min-height: 42px;
  padding: 0 24px;
}

.refresh-btn:hover {
  background: #1e293b;
}
</style>
