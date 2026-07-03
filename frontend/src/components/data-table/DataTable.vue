<script setup lang="ts">
defineProps<{
  columns: { key: string; label: string; width?: string }[]
  rows: Record<string, unknown>[]
  loading?: boolean
}>()

defineEmits<{
  action: [key: string, row: Record<string, unknown>]
}>()
</script>

<template>
  <div class="data-table-wrapper">
    <div v-if="loading" class="data-table__loading">加载中...</div>
    <table v-else-if="rows.length" class="data-table">
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" :style="col.width ? { width: col.width } : undefined">
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in rows" :key="i">
          <td v-for="col in columns" :key="col.key">
            <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
              {{ row[col.key] ?? '-' }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="data-table__empty">暂无数据</div>
  </div>
</template>

<style scoped>
.data-table-wrapper {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.data-table__loading,
.data-table__empty {
  color: var(--color-text-muted);
  font-size: 15px;
  padding: 40px 0;
  text-align: center;
}

.data-table {
  border-collapse: collapse;
  width: 100%;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
  padding: 12px 16px;
  text-align: left;
}

.data-table th {
  background: #f8fafc;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  white-space: nowrap;
}

.data-table tbody tr:hover {
  background: #f8fafc;
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}
</style>
