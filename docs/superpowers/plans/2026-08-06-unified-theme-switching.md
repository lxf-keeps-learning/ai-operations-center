# Unified Theme Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted, site-wide theme switch with vivid light as the default and the existing deep dark palette as the alternate.

**Architecture:** A small Pinia theme store owns the theme union, localStorage persistence, and root `data-theme` synchronization. Global CSS variables define the two palettes; both layouts and their page surfaces consume the variables and expose the same compact switch control.

**Tech Stack:** Vue 3 `<script setup>`, Pinia, TypeScript, scoped CSS, Vite.

## Global Constraints

- Default theme is `vivid-light`.
- Supported themes are `vivid-light` and `deep-night`.
- Theme selection is client-side and persisted in `localStorage`.
- New and legacy layouts must switch together without changing routing or business behavior.
- Do not add backend APIs or new frontend dependencies.

---

### Task 1: Add the theme store and global palette contract

**Files:**
- Create: `frontend/src/stores/theme.ts`
- Modify: `frontend/src/assets/styles/theme.css`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Produces `ThemeName`, `useThemeStore()`, `THEME_STORAGE_KEY`, and `applyTheme(theme)` for layout consumers and startup initialization.
- `useThemeStore().theme` is a `Ref<ThemeName>` exposed by the setup store; `toggleTheme()` switches between the two supported values.

- [x] **Step 1: Define the failing behavior check**

  Verify the current app has no `data-theme` synchronization or persisted theme contract:

  ```bash
  rg -n "data-theme|THEME_STORAGE_KEY|useThemeStore" frontend/src
  ```

  Expected: no theme store or root theme synchronization is present.

- [x] **Step 2: Implement the minimal store and startup hook**

  Add a setup-style Pinia store that safely reads `localStorage`, accepts only the two theme names, updates `document.documentElement.dataset.theme`, and persists changes with a `watch`. Call `useThemeStore().initialize()` after Pinia is installed and before mount in `main.ts`.

- [x] **Step 3: Replace the global color contract**

  Define `:root` defaults for `vivid-light` and a `[data-theme='deep-night']` override covering page background, panel, elevated panel, text, muted text, border, accent, accent-soft, gradient, shadow, and legacy-surface colors. Keep existing generic `--color-*` variables as aliases so existing pages continue to work.

- [x] **Step 4: Verify the contract**

  Run:

  ```bash
  cd frontend && npm run type-check
  ```

  Expected: exit 0 with no TypeScript errors.

### Task 2: Add the shared switch controls to both layouts

**Files:**
- Create: `frontend/src/components/ThemeToggle.vue`
- Modify: `frontend/src/layouts/PlatformLayout.vue`
- Modify: `frontend/src/layouts/DefaultLayout.vue`

**Interfaces:**
- `ThemeToggle` consumes `useThemeStore()` and renders a button with an accessible label, current theme text, and `@click="themeStore.toggleTheme"`.

- [x] **Step 1: Add the component contract**

  Create a button that exposes `aria-label` and `title` based on the next theme, shows a sun/spark icon for vivid light and a moon icon for deep night, and updates its text after switching.

- [x] **Step 2: Mount it in both topbars**

  Place the same component in the `PlatformLayout` topbar actions and the `DefaultLayout` header after the existing navigation/actions. Do not duplicate theme state in either layout.

- [x] **Step 3: Style the control with theme variables**

  Give it a compact pill/button appearance with gradient accent, visible focus ring, hover state, and a mobile-friendly icon-first layout. Keep the existing responsive navigation behavior unchanged.

- [x] **Step 4: Verify the UI integration statically**

  Run:

  ```bash
  rg -n "ThemeToggle|toggleTheme|aria-label" frontend/src/layouts frontend/src/components/ThemeToggle.vue
  ```

  Expected: both layouts reference the same component and no layout owns a separate theme state.

### Task 3: Migrate layout surfaces and hard-coded theme colors

**Files:**
- Modify: `frontend/src/layouts/PlatformLayout.vue`
- Modify: `frontend/src/layouts/DefaultLayout.vue`
- Modify: `frontend/src/pages/HomePage.vue`
- Modify: `frontend/src/components/ReportChatPanel.vue`
- Modify: `frontend/src/components/data-table/DataTable.vue`
- Modify: `frontend/src/components/StatusBadge.vue`
- Modify: `frontend/src/pages/dashboard/IndexPage.vue`
- Modify: remaining legacy page styles that use the shared `--color-*` contract.

**Interfaces:**
- Existing components retain their public props, events, and routing behavior.
- Theme-specific colors are read from CSS variables, while semantic success/warning/error colors remain readable in both themes.

- [x] **Step 1: Convert the platform shell**

  Replace platform shell, sidebar, topbar, content, legacy surface, avatar, active nav, toast, and divider literals with the new `--theme-*` variables. Preserve the current deep-night values in the dark override and use the vivid gradient palette for the default.

- [x] **Step 2: Convert the legacy shell**

  Replace header, brand, nav active/hover, dropdown, and main background literals in `DefaultLayout.vue` with the shared variables.

- [x] **Step 3: Convert the most visible shared surfaces**

  Update HomePage, report chat, data table, status badge, dashboard, and any remaining shared page surface literals found by `rg` so cards, tables, inputs, links, and active states respond consistently.

- [x] **Step 4: Verify no major theme islands remain**

  Run:

  ```bash
  rg -n "#050b1c|#040a1a|#091229|#f3f6fb|#ffffff|#f8fafc|#1e2b51|#3730a3" frontend/src/layouts frontend/src/pages frontend/src/components
  ```

  Expected: remaining matches are limited to intentional semantic colors, content-specific illustrations, or explicit dark code blocks rather than shell/card/theme styling.

### Task 4: Verify build and runtime behavior

**Files:**
- Modify: none unless verification exposes a regression.

- [x] **Step 1: Run the full frontend type check**

  ```bash
  cd frontend && npm run type-check
  ```

- [x] **Step 2: Run the production build**

  ```bash
  cd frontend && npm run build
  ```

- [x] **Step 3: Inspect the final diff and behavior checklist**

  Confirm the diff only covers the theme store, global variables, shared toggle, layout integration, and color migration; then manually check default vivid-light, toggle to deep-night, refresh persistence, both route families, and narrow-screen layout.

- [x] **Step 4: Record the result**

  Report exact verification commands and exit results, and note any remaining intentionally hard-coded semantic colors.
