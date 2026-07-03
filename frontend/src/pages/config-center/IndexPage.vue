<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getRuntime } from '@/api/config'
import type { RuntimeEnv } from '@/types/config'
import StatusCard from '@/components/status-card/StatusCard.vue'

const data = ref<RuntimeEnv | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await getRuntime()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="config-center">
    <h1>配置中心</h1>
    <p class="page-subtitle">当前运行环境与应用配置</p>

    <div v-if="loading" class="page-loading">加载中...</div>
    <p v-else-if="error" class="page-error">{{ error }}</p>

    <section v-if="data" class="config-grid">
      <StatusCard label="运行环境" :value="data.env" tone="info" />
      <StatusCard label="应用名称" :value="data.appName" tone="info" />
      <StatusCard label="版本" :value="data.version" tone="info" />
      <StatusCard label="默认模型" :value="data.defaultModel" tone="success" />
      <StatusCard label="时区" :value="data.timezone" tone="info" />
    </section>
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

.config-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
}
</style>
