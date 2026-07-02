<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { createItem, deleteItem, listItems } from '@/api/runtime'
import type { ItemCreateRequest, ItemResponse } from '@/types/api'

const items = ref<ItemResponse[]>([])
const loading = ref(false)
const error = ref('')
const form = ref<ItemCreateRequest>({ name: '', description: '' })
const submitting = ref(false)

async function fetchItems() {
  loading.value = true
  error.value = ''
  try {
    const result = await listItems({ page: 1, page_size: 100 })
    items.value = result.items
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!form.value.name.trim()) return
  submitting.value = true
  try {
    await createItem({
      name: form.value.name.trim(),
      description: form.value.description?.trim() || null,
    })
    form.value = { name: '', description: '' }
    await fetchItems()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建失败'
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id: number) {
  try {
    await deleteItem(id)
    await fetchItems()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删除失败'
  }
}

onMounted(fetchItems)
</script>

<template>
  <div class="items-page">
    <div class="items-page__header">
      <h1>系统数据管理</h1>
      <span class="items-page__count">共 {{ items.length }} 条</span>
    </div>

    <p v-if="error" class="items-page__error">{{ error }}</p>

    <section class="create-section">
      <h2>新增数据</h2>
      <form class="create-form" @submit.prevent="handleSubmit">
        <input
          v-model="form.name"
          class="create-form__input"
          placeholder="名称"
          required
        />
        <input
          v-model="form.description"
          class="create-form__input"
          placeholder="描述（可选）"
        />
        <button
          class="create-form__btn"
          type="submit"
          :disabled="submitting || !form.name.trim()"
        >
          {{ submitting ? '提交中...' : '新增' }}
        </button>
      </form>
    </section>

    <section class="list-section">
      <h2>数据列表</h2>
      <div v-if="loading" class="list-section__loading">加载中...</div>
      <table v-else-if="items.length" class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>描述</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.id }}</td>
            <td>{{ item.name }}</td>
            <td>{{ item.description || '-' }}</td>
            <td>
              <span class="status-tag" :class="item.is_active ? 'status-tag--active' : 'status-tag--inactive'">
                {{ item.is_active ? '启用' : '停用' }}
              </span>
            </td>
            <td>{{ item.created_at }}</td>
            <td>
              <button class="btn-delete" @click="handleDelete(item.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="list-section__empty">暂无数据</div>
    </section>
  </div>
</template>

<style scoped>
.items-page {
  max-width: 960px;
}

.items-page__header {
  align-items: baseline;
  display: flex;
  gap: 16px;
  margin-bottom: 28px;
}

.items-page__header h1 {
  color: var(--color-heading);
  font-size: 26px;
  margin: 0;
}

.items-page__count {
  color: var(--color-text-muted);
  font-size: 14px;
}

.items-page__error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #b91c1c;
  font-size: 14px;
  margin-bottom: 20px;
  padding: 12px 16px;
}

.create-section,
.list-section {
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 24px;
  padding: 24px;
}

.create-section h2,
.list-section h2 {
  color: var(--color-heading);
  font-size: 18px;
  margin: 0 0 16px;
}

.create-form {
  display: flex;
  gap: 12px;
}

.create-form__input {
  border: 1px solid var(--color-border-strong);
  border-radius: 8px;
  font-size: 15px;
  padding: 10px 14px;
  flex: 1;
  min-width: 0;
}

.create-form__input:focus {
  border-color: #6366f1;
  outline: none;
}

.create-form__btn {
  align-items: center;
  background: #0f172a;
  border: none;
  border-radius: 8px;
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  font-size: 15px;
  font-weight: 800;
  justify-content: center;
  min-height: 42px;
  padding: 0 20px;
  white-space: nowrap;
}

.create-form__btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.list-section__loading,
.list-section__empty {
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
  padding: 12px 8px;
  text-align: left;
}

.data-table th {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.data-table tbody tr:hover {
  background: #f8fafc;
}

.status-tag {
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
}

.status-tag--active {
  background: #f0fdf4;
  color: #166534;
}

.status-tag--inactive {
  background: #fef2f2;
  color: #991b1b;
}

.btn-delete {
  background: none;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #dc2626;
  cursor: pointer;
  font-size: 13px;
  padding: 4px 12px;
}

.btn-delete:hover {
  background: #fef2f2;
}

@media (max-width: 640px) {
  .create-form {
    flex-direction: column;
  }
}
</style>
