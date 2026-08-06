import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const THEME_STORAGE_KEY = 'ioc-theme'

export type ThemeName = 'vivid-light' | 'deep-night'

const DEFAULT_THEME: ThemeName = 'vivid-light'
const THEMES: readonly ThemeName[] = ['vivid-light', 'deep-night']

function isThemeName(value: string | null): value is ThemeName {
  return value !== null && THEMES.includes(value as ThemeName)
}

export function applyTheme(theme: ThemeName) {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = theme
  }
}

function readStoredTheme(): ThemeName {
  if (typeof window === 'undefined') return DEFAULT_THEME

  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
  return isThemeName(storedTheme) ? storedTheme : DEFAULT_THEME
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeName>(DEFAULT_THEME)

  function initialize() {
    theme.value = readStoredTheme()
    applyTheme(theme.value)
  }

  function toggleTheme() {
    theme.value = theme.value === 'vivid-light' ? 'deep-night' : 'vivid-light'
  }

  watch(theme, (nextTheme) => {
    applyTheme(nextTheme)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
    }
  })

  return { theme, initialize, toggleTheme }
})
