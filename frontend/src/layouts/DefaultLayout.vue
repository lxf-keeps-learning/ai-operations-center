<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

import ThemeToggle from '@/components/ThemeToggle.vue'

const infraOpen = ref(false)
const operationOpen = ref(false)

function toggleInfra() {
  infraOpen.value = !infraOpen.value
}

function toggleOperation() {
  operationOpen.value = !operationOpen.value
}

const infraLinks = [
  { to: '/platform', label: 'Agent 控制台' },
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
        <RouterLink to="/prompt-center">Prompt 管理</RouterLink>
        <RouterLink to="/evaluation">质量评估</RouterLink>
        <RouterLink to="/experiments">实验中心</RouterLink>
        <RouterLink to="/failures">失败案例</RouterLink>
        <div class="nav-dropdown">
          <button class="nav-dropdown__trigger" @click="toggleOperation">
            运营分析 <span class="nav-dropdown__arrow">{{ operationOpen ? '▲' : '▼' }}</span>
          </button>
          <div v-if="operationOpen" class="nav-dropdown__menu" @mouseleave="operationOpen = false">
            <RouterLink to="/operation" class="nav-dropdown__item" @click="operationOpen = false">报告分析</RouterLink>
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
      <ThemeToggle />
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
  background: var(--theme-sidebar);
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
  color: var(--theme-text);
  display: inline-flex;
  gap: 12px;
  text-decoration: none;
}

.brand__mark {
  align-items: center;
  background: var(--theme-gradient);
  border-radius: 8px;
  color: var(--theme-accent-contrast);
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
  background: var(--theme-accent-soft);
  color: var(--theme-accent-strong);
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
  background: var(--theme-accent-soft);
}

.nav-dropdown__arrow {
  font-size: 10px;
  margin-left: 4px;
}

.nav-dropdown__menu {
  background: var(--theme-panel-solid);
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
  background: var(--theme-accent-soft);
}

.nav-dropdown__item.router-link-active {
  background: var(--theme-accent-soft);
  color: var(--theme-accent-strong);
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
