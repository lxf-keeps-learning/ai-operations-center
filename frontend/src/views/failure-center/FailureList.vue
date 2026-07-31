<template>
  <div class="failure-list">
    <div class="page-header">
      <div>
        <h1>失败案例中心</h1>
        <p class="subtitle">从线上失败案例中提取 Prompt 优化资产</p>
      </div>
      <div class="header-actions">
        <el-input v-model="filterPromptKey" placeholder="Prompt Key" clearable style="width: 200px" @change="fetchData" />
        <el-select v-model="filterType" placeholder="失败类型" clearable style="width: 140px" @change="fetchData">
          <el-option v-for="(l, k) in TYPE_LABELS" :key="k" :label="l" :value="k" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 110px" @change="fetchData">
          <el-option v-for="(s, k) in STATUS_MAP" :key="k" :label="s.label" :value="k" />
        </el-select>
        <el-button type="primary" @click="batchCollect">自动收集</el-button>
      </div>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="prompt_key" label="Prompt" width="160" />
      <el-table-column label="失败类型" width="140">
        <template #default="{ row }">{{ TYPE_LABELS[row.failure_type] || row.failure_type }}</template>
      </el-table-column>
      <el-table-column label="严重程度" width="90">
        <template #default="{ row }">
          <el-tag :type="SEVERITY_MAP[row.severity]?.type" size="small">{{ SEVERITY_MAP[row.severity]?.label || row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="eval_score" label="评估分" width="80">
        <template #default="{ row }">{{ row.eval_score != null ? (row.eval_score * 100).toFixed(0) + '%' : '-' }}</template>
      </el-table-column>
      <el-table-column prop="reason" label="原因" min-width="250" show-overflow-tooltip />
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="viewDetail(row.id)">详情</el-button>
          <el-button v-if="row.status === 'pending'" link type="success" size="small" @click="doConvert(row.id)">生成用例</el-button>
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
import { ElMessage } from 'element-plus'
import { FAILURE_TYPE_LABELS, SEVERITY_MAP, STATUS_MAP } from '@/types/failure-center'
import * as api from '@/api/failure-center'
import type { FailureSummary } from '@/types/failure-center'

const router = useRouter()
const loading = ref(false)
const items = ref<FailureSummary[]>([])
const total = ref(0)
const page = ref(1)
const filterPromptKey = ref('')
const filterType = ref('')
const filterStatus = ref('')
const TYPE_LABELS = FAILURE_TYPE_LABELS

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try {
    const result = await api.listFailures({
      page: page.value,
      page_size: 20,
      prompt_key: filterPromptKey.value || undefined,
      failure_type: filterType.value || undefined,
      status: filterStatus.value || undefined,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

async function batchCollect() {
  const key = filterPromptKey.value
  if (!key) { ElMessage.warning('请先输入 Prompt Key'); return }
  try {
    const results = await api.autoCollect(key)
    ElMessage.success(`收集到 ${results.length} 个失败案例`)
    fetchData()
  } catch (e: any) {
    ElMessage.error(e.message || '收集失败')
  }
}

async function doConvert(id: number) {
  try {
    await api.convertFailure(id)
    ElMessage.success('已生成测试用例')
    fetchData()
  } catch (e: any) {
    ElMessage.error(e.message || '转化失败')
  }
}

function viewDetail(id: number) {
  router.push(`/failures/${id}`)
}
</script>

<style scoped>
.failure-list { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 24px; }
.subtitle { margin: 8px 0 0; color: #909399; font-size: 14px; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
