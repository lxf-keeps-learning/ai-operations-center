<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  tone?: 'success' | 'warning' | 'danger' | 'info'
}>()
</script>

<template>
  <div class="status-card" :class="tone ? `status-card--${tone}` : ''">
    <span class="status-card__label">{{ label }}</span>
    <strong class="status-card__value">{{ value }}</strong>
  </div>
</template>

<style scoped>
.status-card {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 20px;
}

.status-card__label {
  color: var(--color-text-muted);
  display: block;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 8px;
  text-transform: uppercase;
}

.status-card__value {
  color: var(--color-heading);
  display: block;
  font-size: 22px;
}

.status-card--success .status-card__value { color: #166534; }
.status-card--warning .status-card__value { color: #854d0e; }
.status-card--danger .status-card__value  { color: #991b1b; }
.status-card--info .status-card__value    { color: #1e40af; }
</style>
