<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import ThemeToggle from '@/components/ThemeToggle.vue'

const route = useRoute()
const unavailableMessage = ref('')
let unavailableTimer: ReturnType<typeof setTimeout> | undefined

const navGroups = [
  {
    label: '核心',
    items: [
      { label: '概览', icon: '▦', to: '/platform', match: ['/platform'], available: true },
      { label: '对话', icon: '▢', to: '/platform/conversations', match: ['/platform/conversations'], available: true },
      { label: 'Agent', icon: '♙', to: '/platform/agents', match: ['/platform/agents'], available: true },
      { label: 'Agent Team', icon: '♧', to: '/platform/teams', match: ['/platform/teams'], available: true },
    ],
  },
  {
    label: '运行',
    items: [
      { label: 'Session', icon: '◷', to: '/platform/sessions', match: ['/platform/sessions'], available: true },
      { label: '待处理消息', icon: '▱', to: '/platform/messages', match: ['/platform/messages'], available: true },
      { label: 'Trace', icon: '⌁', to: '/platform/traces', match: ['/platform/traces'], available: true },
      { label: 'Graph 运行', icon: '⌁', to: '/platform/graphs', match: ['/platform/graphs'], available: true },
    ],
  },
  {
    label: '策略与能力',
    items: [
      { label: 'Prompt 策略', icon: '✦', to: '/prompt-center', match: ['/prompt-center'], available: true },
      { label: '模型配置', icon: '◈', to: '/infra/models', match: ['/infra/models'], available: true },
      { label: '内置工具', icon: '◇', to: '/platform', match: ['/platform/tools'], available: false },
      { label: 'Skill', icon: 'ϟ', to: '/platform', match: ['/platform/skills'], available: false },
      { label: 'MCP 服务器', icon: '♧', to: '/platform', match: ['/platform/mcp'], available: false },
    ],
  },
  {
    label: '系统',
    items: [
      { label: '日志中心', icon: '≋', to: '/infra/logs', match: ['/infra/logs'], available: true },
      { label: '健康检查', icon: '♥', to: '/infra/health', match: ['/infra/health'], available: true },
      { label: '配置中心', icon: '⚙', to: '/infra/config', match: ['/infra/config'], available: true },
    ],
  },
]

function isItemActive(item: { match?: string[] }) {
  return item.match?.some((path) => {
    if (route.path === path) return true
    // /platform 是概览根路由，不能因为所有管理页都位于 /platform/* 下而被同时选中。
    return path !== '/platform' && route.path.startsWith(`${path}/`)
  }) ?? false
}

function notifyUnavailable(label: string) {
  unavailableMessage.value = `${label}：功能待开发`
  if (unavailableTimer) clearTimeout(unavailableTimer)
  unavailableTimer = setTimeout(() => {
    unavailableMessage.value = ''
  }, 2600)
}
</script>

<template>
  <div class="platform-shell">
    <aside class="platform-sidebar">
      <RouterLink class="platform-brand" to="/platform">
        <span class="platform-brand__mark">AI</span>
        <span>
          <strong>运营智能体</strong>
          <small>Agent Operations</small>
        </span>
      </RouterLink>

      <nav class="platform-nav" aria-label="Agent 平台导航">
        <section v-for="group in navGroups" :key="group.label" class="platform-nav__group">
          <p>{{ group.label }}</p>
          <template v-for="item in group.items" :key="`${group.label}-${item.label}`">
            <RouterLink
              v-if="item.available"
              :to="item.to"
              class="platform-nav__item"
              :class="{ 'platform-nav__item--active': isItemActive(item) }"
            >
              <span class="platform-nav__icon">{{ item.icon }}</span>
              <span>{{ item.label }}</span>
            </RouterLink>
            <button
              v-else
              type="button"
              class="platform-nav__item platform-nav__item--unavailable"
              :aria-label="`${item.label}，功能待开发`"
              @click="notifyUnavailable(item.label)"
            >
              <span class="platform-nav__icon">{{ item.icon }}</span>
              <span>{{ item.label }}</span>
              <small>待开发</small>
            </button>
          </template>
        </section>
      </nav>

      <div class="platform-sidebar__footer">
        <span class="status-dot status-dot--online" />
        <span>开发环境</span>
        <span class="platform-sidebar__version">v0.1</span>
      </div>
    </aside>

    <Transition name="platform-toast">
      <div v-if="unavailableMessage" class="platform-toast" role="status">
        {{ unavailableMessage }}
      </div>
    </Transition>

    <div class="platform-main">
      <header class="platform-topbar">
        <div class="platform-breadcrumb">AI Operations Center <span>/</span> Platform</div>
        <div class="platform-topbar__actions">
          <ThemeToggle />
          <span class="platform-env"><span class="status-dot status-dot--online" /> 已连接</span>
          <span class="platform-avatar">L</span>
        </div>
      </header>
      <main class="platform-content" :class="{ 'platform-content--legacy': route.meta.platformLegacy }">
        <div v-if="route.meta.platformLegacy" class="platform-legacy-surface">
          <slot />
        </div>
        <slot v-else />
      </main>
    </div>
  </div>
</template>

<style scoped>
.platform-shell {
  background: var(--theme-page);
  color: var(--theme-text);
  display: flex;
  min-height: 100vh;
  width: 100%;
}

.platform-sidebar {
  background: var(--theme-sidebar);
  border-right: 1px solid var(--theme-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  min-height: 100vh;
  padding: 22px 12px 14px;
  width: 238px;
}

.platform-brand {
  align-items: center;
  color: var(--theme-text);
  display: flex;
  gap: 11px;
  margin: 0 10px 34px;
  text-decoration: none;
}

.platform-brand__mark {
  align-items: center;
  background: var(--theme-gradient);
  border-radius: 11px;
  color: var(--theme-accent-contrast);
  display: inline-flex;
  font-size: 13px;
  font-weight: 900;
  height: 37px;
  justify-content: center;
  letter-spacing: -0.06em;
  width: 37px;
}

.platform-brand strong,
.platform-brand small {
  display: block;
}

.platform-brand strong {
  font-size: 14px;
}

.platform-brand small {
  color: var(--theme-muted);
  font-size: 10px;
  margin-top: 3px;
}

.platform-nav {
  display: grid;
  gap: 24px;
}

.platform-nav__group p {
  color: var(--theme-muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.13em;
  margin: 0 12px 8px;
  text-transform: uppercase;
}

.platform-nav__item {
  align-items: center;
  border-radius: 9px;
  color: var(--theme-muted);
  display: flex;
  font-size: 13px;
  gap: 12px;
  margin: 2px 0;
  padding: 10px 12px;
  text-decoration: none;
  transition: background 0.16s ease, color 0.16s ease;
}

.platform-nav__item:hover,
.platform-nav__item--active {
  background: var(--theme-accent-soft);
  color: var(--theme-heading);
}

.platform-nav__item--active {
  box-shadow: inset 3px 0 0 var(--theme-accent);
}

.platform-nav__item--unavailable {
  background: transparent;
  border: 0;
  cursor: not-allowed;
  font: inherit;
  text-align: left;
  width: 100%;
}

.platform-nav__item--unavailable:hover {
  background: var(--theme-accent-soft);
  color: var(--theme-text);
}

.platform-nav__item--unavailable small {
  color: var(--theme-muted);
  font-size: 10px;
  margin-left: auto;
  white-space: nowrap;
}

.platform-nav__icon {
  align-items: center;
  color: var(--theme-muted);
  display: inline-flex;
  font-size: 17px;
  height: 18px;
  justify-content: center;
  width: 18px;
}

.platform-nav__item--active .platform-nav__icon {
  color: var(--theme-accent-strong);
}

.platform-sidebar__footer {
  align-items: center;
  border-top: 1px solid var(--theme-border);
  color: var(--theme-muted);
  display: flex;
  font-size: 11px;
  gap: 7px;
  margin-top: auto;
  padding: 16px 10px 0;
}

.platform-sidebar__version {
  color: var(--theme-muted);
  margin-left: auto;
}

.status-dot {
  border-radius: 50%;
  display: inline-block;
  height: 7px;
  width: 7px;
}

.status-dot--online {
  background: #15c78a;
  box-shadow: 0 0 0 3px rgba(21, 199, 138, 0.12);
}

.platform-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.platform-topbar {
  align-items: center;
  border-bottom: 1px solid var(--theme-border);
  display: flex;
  justify-content: space-between;
  min-height: 62px;
  padding: 0 32px;
}

.platform-breadcrumb {
  color: var(--theme-muted);
  font-size: 12px;
}

.platform-breadcrumb span {
  color: var(--theme-muted);
  margin: 0 8px;
}

.platform-topbar__actions {
  align-items: center;
  display: flex;
  gap: 14px;
}

.platform-env {
  align-items: center;
  color: var(--theme-success-text, #168b68);
  display: flex;
  font-size: 12px;
  gap: 8px;
}

.platform-avatar {
  align-items: center;
  background: var(--theme-accent-soft);
  border-radius: 50%;
  color: var(--theme-accent-strong);
  display: inline-flex;
  font-size: 12px;
  font-weight: 800;
  height: 28px;
  justify-content: center;
  width: 28px;
}

.platform-content {
  margin: 0 auto;
  max-width: 1600px;
  padding: 30px 32px 44px;
  width: 100%;
}

.platform-content--legacy {
  background: var(--theme-page-accent);
}

.platform-legacy-surface {
  background: var(--theme-panel-solid);
  border: 1px solid var(--theme-border);
  border-radius: 12px;
  color: var(--theme-text);
  min-height: calc(100vh - 140px);
  padding: 24px;
}

.platform-toast {
  background: var(--theme-panel-solid);
  border: 1px solid var(--theme-border-strong);
  border-radius: 8px;
  box-shadow: var(--theme-shadow);
  color: var(--theme-text);
  font-size: 12px;
  left: 50%;
  padding: 10px 16px;
  position: fixed;
  top: 76px;
  transform: translateX(-50%);
  z-index: 10;
}

.platform-toast-enter-active,
.platform-toast-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.platform-toast-enter-from,
.platform-toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}

@media (max-width: 800px) {
  .platform-sidebar {
    width: 76px;
  }

  .platform-brand {
    justify-content: center;
    margin-left: 0;
    margin-right: 0;
  }

  .platform-brand > span:last-child,
  .platform-nav__group p,
  .platform-nav__item span:last-child,
  .platform-sidebar__footer span:not(.status-dot) {
    display: none;
  }

  .platform-nav__item {
    justify-content: center;
    padding: 12px 8px;
  }

  .platform-topbar,
  .platform-content {
    padding-left: 20px;
    padding-right: 20px;
  }
}
</style>
