<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

const infraOpen = ref(false)
const operationOpen = ref(false)

function toggleInfra() {
  infraOpen.value = !infraOpen.value
}

function toggleOperation() {
  operationOpen.value = !operationOpen.value
}

const infraLinks = [
  { to: '/infra', label: '控制台' },
  { to: '/infra/config', label: '配置中心' },
  { to: '/infra/models', label: '模型配置' },
  { to: '/infra/logs', label: '日志中心' },
  { to: '/infra/trace', label: 'Trace 查询' },
  { to: '/infra/errors', label: '错误码说明' },
  { to: '/infra/health', label: '健康检查' },
  { to: '/infra/context', label: 'Context 示例' },
]
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/">
        <span class="brand__mark">IOC</span>
        <span>
          <strong>智能运营中心</strong>
          <small>AI Operations Center</small>
        </span>
      </RouterLink>
      <nav class="app-nav" aria-label="主导航">
        <RouterLink to="/">运营总览</RouterLink>
        <RouterLink to="/items">数据管理</RouterLink>
        <div class="nav-dropdown">
          <button class="nav-dropdown__trigger" @click="toggleOperation">
            运营分析 <span class="nav-dropdown__arrow">{{ operationOpen ? '▲' : '▼' }}</span>
          </button>
          <div v-if="operationOpen" class="nav-dropdown__menu" @mouseleave="operationOpen = false">
            <RouterLink to="/operation" class="nav-dropdown__item" @click="operationOpen = false">AI 智能分析</RouterLink>
            <RouterLink to="/operation/records" class="nav-dropdown__item" @click="operationOpen = false">分析记录</RouterLink>
          </div>
        </div>
        <div class="nav-dropdown">
          <button class="nav-dropdown__trigger" @click="toggleInfra">
            基础设施 <span class="nav-dropdown__arrow">{{ infraOpen ? '▲' : '▼' }}</span>
          </button>
          <div v-if="infraOpen" class="nav-dropdown__menu" @mouseleave="infraOpen = false">
            <RouterLink
              v-for="link in infraLinks"
              :key="link.to"
              :to="link.to"
              class="nav-dropdown__item"
              @click="infraOpen = false"
            >
              {{ link.label }}
            </RouterLink>
          </div>
        </div>
      </nav>
    </header>

    <main class="app-main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.app-header {
  align-items: center;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  justify-content: space-between;
  min-height: 72px;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.brand {
  align-items: center;
  color: var(--color-text);
  display: inline-flex;
  gap: 12px;
  text-decoration: none;
}

.brand__mark {
  align-items: center;
  background: #0f172a;
  border-radius: 8px;
  color: #f8fafc;
  display: inline-flex;
  font-size: 14px;
  font-weight: 800;
  height: 36px;
  justify-content: center;
  width: 42px;
}

.brand strong,
.brand small {
  display: block;
}

.brand small {
  color: var(--color-text-muted);
  font-size: 12px;
  margin-top: 2px;
}

.app-nav {
  align-items: center;
  display: flex;
  gap: 8px;
}

.app-nav > a {
  border-radius: 8px;
  color: var(--color-text-muted);
  font-size: 14px;
  font-weight: 700;
  padding: 10px 12px;
  text-decoration: none;
  white-space: nowrap;
}

.app-nav > a.router-link-active {
  background: #eef2ff;
  color: #3730a3;
}

.nav-dropdown {
  position: relative;
}

.nav-dropdown__trigger {
  background: none;
  border: none;
  border-radius: 8px;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
  padding: 10px 12px;
  white-space: nowrap;
}

.nav-dropdown__trigger:hover {
  background: #f1f5f9;
}

.nav-dropdown__arrow {
  font-size: 10px;
  margin-left: 4px;
}

.nav-dropdown__menu {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  min-width: 160px;
  padding: 6px;
  position: absolute;
  right: 0;
  top: 100%;
}

.nav-dropdown__item {
  border-radius: 6px;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 600;
  padding: 8px 12px;
  text-decoration: none;
  white-space: nowrap;
}

.nav-dropdown__item:hover {
  background: #f1f5f9;
}

.nav-dropdown__item.router-link-active {
  background: #eef2ff;
  color: #3730a3;
}

.app-main {
  margin: 0 auto;
  max-width: 1760px;
  padding: 20px 24px 28px;
}

@media (max-width: 720px) {
  .app-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
    padding: 18px 20px;
  }

  .app-nav {
    max-width: 100%;
    overflow-x: auto;
    padding-bottom: 2px;
    width: 100%;
  }

  .app-main {
    padding: 24px 18px;
  }
}
</style>
