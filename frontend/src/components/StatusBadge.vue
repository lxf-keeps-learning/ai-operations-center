<script setup lang="ts">
type Tone = 'success' | 'warning' | 'danger' | 'neutral' | 'info'

defineProps<{
  tone?: Tone
  label: string
}>()
</script>

<template>
  <span class="status-badge" :class="`status-badge--${tone || 'neutral'}`">
    <span class="status-badge__dot" />
    {{ label }}
  </span>
</template>

<style scoped>
.status-badge {
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  display: inline-flex;
  font-size: 13px;
  font-weight: 600;
  gap: 8px;
  line-height: 1;
  padding: 8px 10px;
  white-space: nowrap;
}

.status-badge__dot {
  border-radius: 50%;
  display: inline-block;
  height: 8px;
  width: 8px;
}

.status-badge--success {
  background: var(--theme-success-soft, #ecfdf5);
  color: var(--theme-success-text, #047857);
}

.status-badge--success .status-badge__dot {
  background: #10b981;
}

.status-badge--warning {
  background: var(--theme-warning-soft, #fffbeb);
  color: var(--theme-warning-text, #b45309);
}

.status-badge--warning .status-badge__dot {
  background: #f59e0b;
}

.status-badge--danger {
  background: var(--theme-danger-soft, #fef2f2);
  color: var(--theme-danger-text, #b91c1c);
}

.status-badge--danger .status-badge__dot {
  background: #ef4444;
}

.status-badge--info {
  background: var(--theme-info-soft, #eff6ff);
  color: var(--theme-info-text, #1d4ed8);
}

.status-badge--info .status-badge__dot {
  background: #3b82f6;
}

.status-badge--neutral {
  background: var(--theme-panel-soft);
  color: var(--theme-muted);
}

.status-badge--neutral .status-badge__dot {
  background: #94a3b8;
}
</style>
