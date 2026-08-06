<script setup lang="ts">
import { computed } from 'vue'

import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const isVivid = computed(() => themeStore.theme === 'vivid-light')
const nextThemeLabel = computed(() => (isVivid.value ? '深色霓虹' : '明亮绚丽'))
</script>

<template>
  <button
    class="theme-toggle"
    type="button"
    :aria-label="`切换到${nextThemeLabel}主题`"
    :title="`切换到${nextThemeLabel}主题`"
    @click="themeStore.toggleTheme"
  >
    <span class="theme-toggle__icon" aria-hidden="true">{{ isVivid ? '☼' : '☾' }}</span>
    <span class="theme-toggle__label">{{ isVivid ? '明亮绚丽' : '深色霓虹' }}</span>
  </button>
</template>

<style scoped>
.theme-toggle {
  align-items: center;
  background: var(--theme-panel);
  border: 1px solid var(--theme-border);
  border-radius: 999px;
  box-shadow: var(--theme-shadow-soft);
  color: var(--theme-text);
  cursor: pointer;
  display: inline-flex;
  font-size: 11px;
  font-weight: 750;
  gap: 7px;
  min-height: 30px;
  padding: 4px 11px 4px 6px;
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.theme-toggle:hover {
  background: var(--theme-accent-soft);
  border-color: var(--theme-border-strong);
  color: var(--theme-accent-strong);
  transform: translateY(-1px);
}

.theme-toggle:focus-visible {
  outline: 3px solid var(--theme-focus);
  outline-offset: 2px;
}

.theme-toggle__icon {
  align-items: center;
  background: var(--theme-gradient);
  border-radius: 50%;
  color: var(--theme-accent-contrast);
  display: inline-flex;
  font-size: 16px;
  height: 22px;
  justify-content: center;
  line-height: 1;
  width: 22px;
}

@media (max-width: 800px) {
  .theme-toggle {
    padding-right: 7px;
  }

  .theme-toggle__label {
    display: none;
  }
}
</style>
