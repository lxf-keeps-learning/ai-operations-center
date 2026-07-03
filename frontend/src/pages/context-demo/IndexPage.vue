<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getCurrentContext, type ContextData } from '@/api/context'

const context = ref<ContextData | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    context.value = await getCurrentContext()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="context-demo">
    <h1>Context 示例</h1>
    <p class="page-subtitle">当前请求的三层上下文（RequestContext / UserContext / PageContext）</p>

    <div v-if="loading" class="page-loading">加载中...</div>
    <p v-else-if="error" class="page-error">{{ error }}</p>

    <template v-if="context">
      <section class="context-section">
        <h2>RequestContext（请求上下文）</h2>
        <pre>{{ JSON.stringify(context.requestContext, null, 2) }}</pre>
      </section>

      <section class="context-section">
        <h2>UserContext（用户上下文）</h2>
        <pre>{{ JSON.stringify(context.userContext, null, 2) }}</pre>
      </section>

      <section class="context-section">
        <h2>PageContext（页面上下文）</h2>
        <pre>{{ JSON.stringify(context.pageContext, null, 2) }}</pre>
      </section>
    </template>
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

.context-section {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 16px;
  padding: 24px;
}

.context-section h2 {
  color: var(--color-heading);
  font-size: 18px;
  margin: 0 0 12px;
}

.context-section pre {
  background: #101828;
  border-radius: 8px;
  color: #e0f2fe;
  font-size: 13px;
  line-height: 1.7;
  margin: 0;
  overflow-x: auto;
  padding: 20px;
}
</style>
