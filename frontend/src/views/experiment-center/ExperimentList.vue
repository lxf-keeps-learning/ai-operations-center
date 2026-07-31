<template>
  <div class="exp-list">
    <div class="page-header">
      <div>
        <h1>Prompt 实验中心</h1>
        <p class="subtitle">对比不同 Prompt 版本的效果，选择最佳版本</p>
      </div>
      <el-button type="primary" @click="router.push('/experiments/create')">创建实验</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="name" label="实验名称" min-width="200" />
      <el-table-column label="源版本" width="100">
        <template #default="{ row }"><el-tag size="small">v{{ row.source_version }}</el-tag></template>
      </el-table-column>
      <el-table-column label="目标版本" width="100">
        <template #default="{ row }"><el-tag size="small" type="warning">v{{ row.target_version }}</el-tag></template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ STATUS_MAP[row.status as 'pending' | 'running' | 'completed' | 'failed'] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="胜出" width="140">
        <template #default="{ row }">
          <el-tag v-if="row.winner_version === 'source'" type="success" size="small">源版本</el-tag>
          <el-tag v-else-if="row.winner_version === 'target'" type="warning" size="small">目标版本</el-tag>
          <el-tag v-else-if="row.winner_version === 'draw'" size="small">平局</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="total_samples" label="样本数" width="80" />
      <el-table-column prop="created_by" label="创建人" width="120" />
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" link type="primary" size="small" @click="runExp(row.id)">运行</el-button>
          <el-button link type="success" size="small" @click="viewCompare(row.id)">对比</el-button>
          <el-button link type="info" size="small" @click="viewDetail(row.id)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination" v-if="total > 20">
      <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="fetchData" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EXPERIMENT_STATUS_MAP } from '@/types/experiment-center'
import * as api from '@/api/experiment-center'
import type { ExperimentSummary } from '@/types/experiment-center'

const router = useRouter()
const loading = ref(false)
const items = ref<ExperimentSummary[]>([])
const total = ref(0)
const page = ref(1)
const STATUS_MAP = EXPERIMENT_STATUS_MAP

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try {
    const result = await api.listExperiments(page.value)
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function statusType(s: string) {
  const map: Record<string, string> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
  return map[s] || 'info'
}

async function runExp(id: number) {
  try {
    await ElMessageBox.confirm('确认运行此实验？实验会消耗 LLM Token。', '确认')
  } catch { return }
  try {
    await api.runExperiment(id)
    ElMessage.success('实验运行完成')
    fetchData()
  } catch (e: any) {
    ElMessage.error(e.message || '运行失败')
  }
}

function viewCompare(id: number) {
  router.push(`/experiments/${id}/compare`)
}

function viewDetail(id: number) {
  router.push(`/experiments/${id}`)
}
</script>

<style scoped>
.exp-list { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 24px; }
.subtitle { margin: 8px 0 0; color: #909399; font-size: 14px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
