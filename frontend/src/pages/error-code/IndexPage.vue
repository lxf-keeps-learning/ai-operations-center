<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getErrorCodes } from '@/api/errors'
import type { ErrorCodeEntry } from '@/types/error-code'

const codes = ref<ErrorCodeEntry[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    codes.value = await getErrorCodes()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})

function httpStatusClass(status: number) {
  if (status < 300) return 'tag tag--success'
  if (status < 500) return 'tag tag--warning'
  return 'tag tag--danger'
}
</script>

<template>
  <div class="error-code-page">
    <h1>业务错误码说明</h1>
    <p class="page-subtitle">本项目 HTTP 状态码与业务错误码规范</p>

    <div v-if="loading" class="page-loading">加载中...</div>
    <p v-else-if="error" class="page-error">{{ error }}</p>

    <table v-else class="code-table">
      <thead>
        <tr>
          <th>code</th>
          <th>message</th>
          <th>HTTP 状态码</th>
          <th>说明</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in codes" :key="c.code">
          <td><code>{{ c.code }}</code></td>
          <td>{{ c.message }}</td>
          <td>
            <span :class="httpStatusClass(c.httpStatus)" class="tag">{{ c.httpStatus }}</span>
          </td>
          <td>{{ c.description }}</td>
        </tr>
      </tbody>
    </table>
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

.code-table {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-collapse: collapse;
  border-radius: 8px;
  overflow: hidden;
  width: 100%;
}

.code-table th,
.code-table td {
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
  padding: 12px 16px;
  text-align: left;
}

.code-table th {
  background: #f8fafc;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  white-space: nowrap;
}

.code-table tbody tr:hover {
  background: #f8fafc;
}

.code-table code {
  background: #f1f5f9;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 13px;
  padding: 2px 8px;
}

.tag {
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
}

.tag--success { background: #f0fdf4; color: #166534; }
.tag--warning { background: #fffbeb; color: #854d0e; }
.tag--danger  { background: #fef2f2; color: #991b1b; }
</style>
