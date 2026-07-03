<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getRuntime } from '@/api/config'
import { getHealth } from '@/api/health'
import type { RuntimeEnv } from '@/types/config'
import type { HealthData } from '@/api/health'

const runtime = ref<RuntimeEnv | null>(null)
const health = ref<HealthData | null>(null)
const loading = ref(true)
const error = ref('')

const infraPages = [
  { path: '/infra/config', name: '配置中心', desc: '查看当前运行环境与配置' },
  { path: '/infra/models', name: '模型配置', desc: '查看可选模型及参数' },
  { path: '/infra/logs', name: '日志中心', desc: '查看 API 和 LLM 调用日志' },
  { path: '/infra/trace', name: 'Trace 查询', desc: '按 traceId 查询全链路' },
  { path: '/infra/errors', name: '错误码说明', desc: '查看业务错误码对照表' },
  { path: '/infra/health', name: '健康检查', desc: '查看后端服务状态' },
  { path: '/infra/context', name: 'Context 示例', desc: '查看当前请求上下文' },
]

onMounted(async () => {
  try {
    const [r, h] = await Promise.all([getRuntime(), getHealth()])
    runtime.value = r
    health.value = h
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="dashboard">
    <h1>基础设施控制台</h1>
    <p class="dashboard__subtitle">Sprint1 — 基础设施底座建设</p>

    <div v-if="loading" class="dashboard__loading">加载中...</div>
    <p v-else-if="error" class="dashboard__error">{{ error }}</p>

    <section v-if="runtime" class="dashboard__summary">
      <div class="summary-card">
        <span>运行环境</span>
        <strong>{{ runtime.env }}</strong>
      </div>
      <div class="summary-card">
        <span>应用版本</span>
        <strong>{{ runtime.version }}</strong>
      </div>
      <div class="summary-card">
        <span>默认模型</span>
        <strong>{{ runtime.defaultModel }}</strong>
      </div>
      <div class="summary-card">
        <span>后端状态</span>
        <strong :class="health?.status === 'UP' ? 'text-success' : 'text-danger'">
          {{ health?.status || '未知' }}
        </strong>
      </div>
    </section>

    <section class="dashboard__grid">
      <RouterLink v-for="page in infraPages" :key="page.path" class="infra-card" :to="page.path">
        <h3>{{ page.name }}</h3>
        <p>{{ page.desc }}</p>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped>
.dashboard h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0 0 4px;
}

.dashboard__subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin: 0 0 24px;
}

.dashboard__loading,
.dashboard__error {
  margin-bottom: 20px;
  font-size: 15px;
}

.dashboard__error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  padding: 12px 16px;
}

.dashboard__summary {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  margin-bottom: 28px;
}

.summary-card {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
}

.summary-card span {
  color: var(--color-text-muted);
  display: block;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 8px;
  text-transform: uppercase;
}

.summary-card strong {
  color: var(--color-heading);
  font-size: 22px;
}

.text-success { color: #166534; }
.text-danger  { color: #991b1b; }

.dashboard__grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}

.infra-card {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  cursor: pointer;
  display: block;
  padding: 24px;
  text-decoration: none;
  transition: border-color 0.15s;
}

.infra-card:hover {
  border-color: #6366f1;
}

.infra-card h3 {
  color: var(--color-heading);
  font-size: 18px;
  margin: 0 0 8px;
}

.infra-card p {
  color: var(--color-text-muted);
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}
</style>
