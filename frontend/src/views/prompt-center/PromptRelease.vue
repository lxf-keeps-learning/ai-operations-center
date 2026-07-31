<template>
  <div class="prompt-release" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/prompt-center' }">Prompt 管理</el-breadcrumb-item>
        <el-breadcrumb-item :to="{ path: `/prompt-center/${promptId}` }">{{ prompt?.prompt_name || '发布' }}</el-breadcrumb-item>
        <el-breadcrumb-item>发布管理</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <el-card class="section-card">
      <template #header><span>版本信息</span></template>
      <el-table :data="versions" stripe size="small" @row-click="selectVersion">
        <el-table-column prop="version" label="版本号" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="change_reason" label="修改原因" />
        <el-table-column prop="created_by" label="创建人" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
      </el-table>
    </el-card>

    <el-card class="section-card">
      <template #header><span>发布操作</span></template>
      <el-form :model="releaseForm" label-width="100px">
        <el-form-item label="发布版本">
          <el-tag v-if="selectedVersion">v{{ selectedVersion.version }}</el-tag>
          <span v-else style="color: #909399">请在上方选择一个版本</span>
        </el-form-item>
        <el-form-item label="发布环境">
          <el-select v-model="releaseForm.environment">
            <el-option v-for="env in ENVIRONMENT_OPTIONS" :key="env.value" :label="env.label" :value="env.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布方式">
          <el-radio-group v-model="releaseForm.release_type">
            <el-radio value="full">全量发布</el-radio>
            <el-radio value="gray">灰度发布</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="灰度比例" v-if="releaseForm.release_type === 'gray'">
          <el-slider v-model="releaseForm.traffic_ratio" :min="1" :max="100" :format-tooltip="(v: number) => `${v}%`" style="width: 300px" />
        </el-form-item>
        <el-form-item label="发布说明">
          <el-input v-model="releaseForm.release_note" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doPublish" :loading="publishing">
            {{ releaseForm.release_type === 'gray' ? '灰度发布' : '正式发布' }}
          </el-button>
          <el-button @click="doRollback" :loading="rollingBack" :disabled="!releases.length">回滚</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="section-card">
      <template #header><span>发布历史</span></template>
      <el-timeline v-if="releases.length">
        <el-timeline-item
          v-for="r in releases" :key="r.id"
          :timestamp="r.released_at"
          :type="r.release_type === 'rollback' ? 'danger' : 'primary'"
        >
          <div class="release-item">
            <el-tag size="small">v{{ r.version_id }}</el-tag>
            <span>{{ r.environment }}</span>
            <el-tag size="small" :type="r.release_type === 'rollback' ? 'danger' : 'success'">{{ releaseTypeLabel(r) }}</el-tag>
            <span v-if="r.release_note">- {{ r.release_note }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无发布记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { PROMPT_STATUS_MAP, ENVIRONMENT_OPTIONS } from '@/types/prompt-center'
import * as api from '@/api/prompt-center'
import type { PromptDetail, PromptVersionSummary, Release } from '@/types/prompt-center'

const route = useRoute()
const promptId = computed(() => Number(route.params.id))
const loading = ref(false)
const publishing = ref(false)
const rollingBack = ref(false)
const prompt = ref<PromptDetail | null>(null)
const versions = ref<PromptVersionSummary[]>([])
const releases = ref<Release[]>([])
const selectedVersion = ref<PromptVersionSummary | null>(null)
const statusMap = PROMPT_STATUS_MAP

const releaseForm = reactive({
  environment: 'production',
  release_type: 'full',
  traffic_ratio: 10,
  release_note: '',
})

onMounted(async () => {
  loading.value = true
  try {
    prompt.value = await api.getPrompt(promptId.value)
    versions.value = prompt.value.versions || []
    releases.value = await api.listReleases(promptId.value)
  } finally {
    loading.value = false
  }
})

function selectVersion(row: PromptVersionSummary) {
  selectedVersion.value = row
}

function statusType(status: string) {
  const map: Record<string, string> = { draft: 'info', testing: 'warning', reviewing: 'warning', approved: 'success', rejected: 'danger', gray: 'warning', published: 'success', offline: 'info', archived: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  return statusMap[status as keyof typeof statusMap] || status
}

function releaseTypeLabel(r: Release) {
  const map: Record<string, string> = { full: '全量发布', gray: '灰度发布', ab_test: 'A/B 测试', rollback: '回滚' }
  return map[r.release_type] || r.release_type
}

async function doPublish() {
  if (!selectedVersion.value) {
    ElMessage.warning('请先选择一个版本')
    return
  }
  try {
    await ElMessageBox.confirm(`确认将 v${selectedVersion.value.version} 发布到 ${releaseForm.environment} 环境？`, '确认发布')
  } catch { return }

  publishing.value = true
  try {
    if (releaseForm.release_type === 'gray') {
      const r = await api.grayRelease(promptId.value, selectedVersion.value.id, releaseForm as any)
      ElMessage.success(`灰度发布成功，版本 ID: ${r.id}`)
    } else {
      const r = await api.publishVersion(promptId.value, selectedVersion.value.id, releaseForm as any)
      ElMessage.success(`发布成功，版本 ID: ${r.id}`)
    }
    releases.value = await api.listReleases(promptId.value)
  } catch (e: any) {
    ElMessage.error(e.message || '发布失败')
  } finally {
    publishing.value = false
  }
}

async function doRollback() {
  try {
    await ElMessageBox.confirm('确认回滚到上一个版本？', '确认回滚')
  } catch { return }

  rollingBack.value = true
  try {
    const r = await api.rollbackVersion(promptId.value, releaseForm.environment, '回滚到上一版本')
    ElMessage.success(`回滚成功，版本 ID: ${r.id}`)
    releases.value = await api.listReleases(promptId.value)
  } catch (e: any) {
    ElMessage.error(e.message || '回滚失败')
  } finally {
    rollingBack.value = false
  }
}
</script>

<style scoped>
.prompt-release { padding: 24px; }
.page-header { margin-bottom: 24px; }
.section-card { margin-top: 16px; }
.release-item { display: flex; align-items: center; gap: 8px; }
</style>
