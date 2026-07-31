<template>
  <div class="prompt-list">
    <div class="page-header">
      <h1>AI 策略与 Prompt 管理中心</h1>
      <p class="subtitle">统一管理 AI Agent 的 Prompt 策略、版本和发布</p>
    </div>

    <div class="search-bar">
      <el-form :inline="true" :model="filters">
        <el-form-item label="搜索">
          <el-input v-model="filters.search" placeholder="名称 / Prompt Key" clearable @clear="search" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable @change="search">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务场景">
          <el-input v-model="filters.business_scene" placeholder="业务场景" clearable @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="Graph">
          <el-input v-model="filters.graph_name" placeholder="所属 Graph" clearable @keyup.enter="search" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="success" @click="showCreateDialog">新建 Prompt</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="store.promptList" v-loading="store.loading" stripe style="width: 100%">
      <el-table-column prop="prompt_key" label="Prompt Key" width="180" />
      <el-table-column prop="prompt_name" label="名称" min-width="200" />
      <el-table-column prop="business_scene" label="业务场景" width="120" />
      <el-table-column prop="graph_name" label="所属 Graph" width="140" />
      <el-table-column prop="node_name" label="所属 Node" width="140" />
      <el-table-column label="当前版本" width="100">
        <template #default="{ row }">
          <el-tag size="small" v-if="row.current_version_id">v{{ row.current_version_id }}</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updated_by" label="最近修改人" width="120" />
      <el-table-column prop="updated_at" label="更新时间" width="170" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="viewDetail(row.id)">详情</el-button>
          <el-button link type="warning" size="small" @click="editPrompt(row.id)">编辑</el-button>
          <el-button link type="success" size="small" @click="testPrompt(row.id)">测试</el-button>
          <el-button link type="info" size="small" @click="viewMetrics(row.id)">指标</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="store.currentPage"
        :page-size="store.pageSize"
        :total="store.total"
        layout="total, prev, pager, next"
        @current-change="store.fetchPrompts"
      />
    </div>

    <el-dialog v-model="createDialogVisible" title="新建 Prompt" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="Prompt Key" required>
          <el-input v-model="createForm.prompt_key" placeholder="ioc.safety.analysis" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="createForm.prompt_name" />
        </el-form-item>
        <el-form-item label="业务场景">
          <el-input v-model="createForm.business_scene" />
        </el-form-item>
        <el-form-item label="所属 Graph">
          <el-input v-model="createForm.graph_name" />
        </el-form-item>
        <el-form-item label="所属 Node">
          <el-input v-model="createForm.node_name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePromptCenterStore } from '@/stores/prompt-center'
import { PROMPT_STATUS_MAP, PROMPT_STATUS_OPTIONS } from '@/types/prompt-center'
import * as api from '@/api/prompt-center'

const router = useRouter()
const store = usePromptCenterStore()

const statusMap = PROMPT_STATUS_MAP
const statusOptions = PROMPT_STATUS_OPTIONS
const createDialogVisible = ref(false)
const creating = ref(false)

const filters = reactive({
  search: '',
  status: '',
  business_scene: '',
  graph_name: '',
})

const createForm = reactive({
  prompt_key: '',
  prompt_name: '',
  business_scene: '',
  graph_name: '',
  node_name: '',
  description: '',
})

onMounted(() => {
  store.fetchPrompts()
})

function statusType(status: string) {
  const map: Record<string, string> = {
    draft: 'info', testing: 'warning', reviewing: 'warning',
    approved: 'success', rejected: 'danger', gray: 'warning',
    published: 'success', offline: 'info', archived: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  return statusMap[status as keyof typeof statusMap] || status
}

function search() {
  store.searchQuery = filters.search
  store.statusFilter = filters.status
  store.sceneFilter = filters.business_scene
  store.graphFilter = filters.graph_name
  store.fetchPrompts()
}

function resetFilters() {
  filters.search = ''
  filters.status = ''
  filters.business_scene = ''
  filters.graph_name = ''
  store.searchQuery = ''
  store.statusFilter = ''
  store.sceneFilter = ''
  store.graphFilter = ''
  store.fetchPrompts()
}

function showCreateDialog() {
  createDialogVisible.value = true
}

async function handleCreate() {
  if (!createForm.prompt_key || !createForm.prompt_name) return
  creating.value = true
  try {
    await api.createPrompt(createForm as any)
    createDialogVisible.value = false
    createForm.prompt_key = ''
    createForm.prompt_name = ''
    createForm.business_scene = ''
    createForm.graph_name = ''
    createForm.node_name = ''
    createForm.description = ''
    store.fetchPrompts()
  } finally {
    creating.value = false
  }
}

function viewDetail(id: number) {
  router.push(`/prompt-center/${id}`)
}

function editPrompt(id: number) {
  router.push(`/prompt-center/${id}/edit`)
}

function testPrompt(id: number) {
  router.push(`/prompt-center/${id}/test`)
}

function viewMetrics(id: number) {
  router.push(`/prompt-center/${id}/metrics`)
}
</script>

<style scoped>
.prompt-list { padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 24px; }
.subtitle { color: #909399; margin: 8px 0 0; font-size: 14px; }
.search-bar { margin-bottom: 16px; padding: 16px; background: #fff; border-radius: 8px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
