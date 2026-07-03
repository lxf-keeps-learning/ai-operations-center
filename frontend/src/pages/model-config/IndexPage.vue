<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getModels } from '@/api/config'
import type { ModelProvider } from '@/types/config'

const models = ref<ModelProvider[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    models.value = await getModels()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="model-config">
    <h1>模型配置</h1>
    <p class="page-subtitle">可选模型列表（API Key 仅存储在后端，不向前端暴露）</p>

    <div v-if="loading" class="page-loading">加载中...</div>
    <p v-else-if="error" class="page-error">{{ error }}</p>

    <section v-for="m in models" :key="m.provider" class="model-card">
      <div class="model-card__header">
        <h2>{{ m.displayName }}</h2>
        <span class="model-card__provider">{{ m.provider }}</span>
        <span v-if="m.default" class="model-card__badge model-card__badge--default">默认</span>
        <span v-if="!m.enabled" class="model-card__badge model-card__badge--disabled">已禁用</span>
      </div>
      <table class="model-card__table">
        <tr>
          <td>模型</td>
          <td><code>{{ m.model }}</code></td>
        </tr>
        <tr>
          <td>最大输入 Token</td>
          <td>{{ m.maxInputTokens.toLocaleString() }}</td>
        </tr>
        <tr>
          <td>最大输出 Token</td>
          <td>{{ m.maxOutputTokens.toLocaleString() }}</td>
        </tr>
        <tr>
          <td>每分钟请求限制</td>
          <td>{{ m.rpmLimit }} RPM</td>
        </tr>
      </table>
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

.model-card {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 24px;
}

.model-card__header {
  align-items: center;
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.model-card__header h2 {
  color: var(--color-heading);
  font-size: 20px;
  margin: 0;
}

.model-card__provider {
  color: var(--color-text-muted);
  font-family: ui-monospace, monospace;
  font-size: 13px;
}

.model-card__badge {
  border-radius: 4px;
  font-size: 11px;
  font-weight: 800;
  padding: 2px 8px;
  text-transform: uppercase;
}

.model-card__badge--default {
  background: #f0fdf4;
  color: #166534;
}

.model-card__badge--disabled {
  background: #fef2f2;
  color: #991b1b;
}

.model-card__table {
  width: 100%;
}

.model-card__table td {
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
  padding: 10px 0;
}

.model-card__table td:first-child {
  color: var(--color-text-muted);
  width: 160px;
}

.model-card__table td code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  padding: 2px 8px;
}
</style>
