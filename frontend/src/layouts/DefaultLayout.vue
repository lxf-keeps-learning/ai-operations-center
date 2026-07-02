<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/">
        <span class="brand__mark">AI</span>
        <span>
          <strong>智能运营中心</strong>
          <small>Agent Runtime Console</small>
        </span>
      </RouterLink>
      <nav class="app-nav" aria-label="主导航">
        <RouterLink to="/">工作台</RouterLink>
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
  width: 36px;
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

.app-nav a {
  border-radius: 8px;
  color: var(--color-text-muted);
  font-size: 14px;
  font-weight: 700;
  padding: 10px 12px;
  text-decoration: none;
}

.app-nav a.router-link-active {
  background: #eef2ff;
  color: #3730a3;
}

.app-main {
  margin: 0 auto;
  max-width: 1240px;
  padding: 32px;
}

@media (max-width: 720px) {
  .app-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
    padding: 18px 20px;
  }

  .app-main {
    padding: 24px 18px;
  }
}
</style>
