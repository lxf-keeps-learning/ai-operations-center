<template>
  <div class="prompt-detail" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/prompt-center' }">Prompt 管理</el-breadcrumb-item>
        <el-breadcrumb-item>{{ prompt?.prompt_name || '详情' }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <template v-if="prompt">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="业务视图" name="business">
          <el-descriptions title="基础信息" :column="2" border>
            <el-descriptions-item label="名称">{{ prompt.prompt_name }}</el-descriptions-item>
            <el-descriptions-item label="Prompt Key">{{ prompt.prompt_key }}</el-descriptions-item>
            <el-descriptions-item label="业务场景">{{ prompt.business_scene || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所属 Graph">{{ prompt.graph_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusType(prompt.status)" size="small">{{ statusMap[prompt.status] }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="负责人">{{ prompt.owner_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="最近修改人">{{ prompt.updated_by || '-' }}</el-descriptions-item>
            <el-descriptions-item label="最近修改时间">{{ prompt.updated_at }}</el-descriptions-item>
          </el-descriptions>

          <el-card v-if="currentVersion" class="section-card">
            <template #header>
              <span>业务规则 (v{{ currentVersion.version }})</span>
            </template>
            <div v-if="currentVersion.business_role_content" class="section">
              <h4>角色定义</h4>
              <pre>{{ currentVersion.business_role_content }}</pre>
            </div>
            <div v-if="currentVersion.business_goal_content" class="section">
              <h4>业务目标</h4>
              <pre>{{ currentVersion.business_goal_content }}</pre>
            </div>
            <div v-if="currentVersion.business_rules?.length" class="section">
              <h4>分析规则</h4>
              <ol>
                <li v-for="r in currentVersion.business_rules" :key="r.key">
                  <span :class="{ strikethrough: !r.enabled }">{{ r.content }}</span>
                  <el-tag v-if="r.required" size="small" type="danger" style="margin-left: 8px">必填</el-tag>
                </li>
              </ol>
            </div>
            <div v-if="currentVersion.output_requirement" class="section">
              <h4>输出要求</h4>
              <pre>{{ currentVersion.output_requirement }}</pre>
            </div>
          </el-card>

          <el-card class="section-card">
            <template #header><span>动态变量</span></template>
            <el-table :data="prompt.variables" stripe size="small">
              <el-table-column prop="variable_key" label="变量 Key" width="160" />
              <el-table-column prop="variable_name" label="名称" width="140" />
              <el-table-column prop="description" label="说明" />
              <el-table-column prop="data_type" label="类型" width="80" />
              <el-table-column prop="source_type" label="来源" width="100" />
              <el-table-column label="必填" width="60">
                <template #default="{ row }"><el-tag v-if="row.required" size="small" type="danger">是</el-tag><span v-else>否</span></template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="完整视图" name="full">
          <el-alert title="以下为最终发送给模型的完整 Prompt 内容" type="info" show-icon :closable="false" style="margin-bottom: 16px" />
          <el-card v-if="renderedMessages.length">
            <div v-for="(msg, i) in renderedMessages" :key="i" class="message-block">
              <div class="message-role">{{ msg.role === 'system' ? 'System Message' : 'User Message' }}</div>
              <pre class="message-content">{{ msg.content }}</pre>
            </div>
          </el-card>
          <el-empty v-else description="请先选择一个版本预览" />
        </el-tab-pane>

        <el-tab-pane label="版本历史" name="versions">
          <el-timeline v-if="prompt.versions.length">
            <el-timeline-item
              v-for="v in prompt.versions" :key="v.id"
              :timestamp="v.created_at"
              :type="statusType(v.status)"
            >
              <div class="version-item">
                <el-tag size="small" :type="statusType(v.status)">v{{ v.version }}</el-tag>
                <span class="version-status">{{ statusMap[v.status] }}</span>
                <span class="version-reason" v-if="v.change_reason">- {{ v.change_reason }}</span>
                <div class="version-actions">
                  <el-button link type="primary" size="small" @click="previewVersion(v.id)">预览</el-button>
                  <el-button link type="success" size="small" @click="compareWith(v.id)">对比</el-button>
                  <el-button v-if="v.status === 'draft' || v.status === 'rejected'" link type="warning" size="small" @click="submitReview(v.id)">提交审核</el-button>
                  <el-button v-if="v.status === 'reviewing'" link type="success" size="small" @click="approveReview(v.id)">通过</el-button>
                  <el-button v-if="v.status === 'reviewing'" link type="danger" size="small" @click="rejectReview(v.id)">驳回</el-button>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无版本" />
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { PROMPT_STATUS_MAP } from '@/types/prompt-center'
import * as api from '@/api/prompt-center'
import type { PromptDetail, PromptVersion } from '@/types/prompt-center'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const prompt = ref<PromptDetail | null>(null)
const activeTab = ref('business')
const currentVersion = ref<PromptVersion | null>(null)
const renderedMessages = ref<any[]>([])
const statusMap = PROMPT_STATUS_MAP

const promptId = computed(() => Number(route.params.id))

onMounted(async () => {
  loading.value = true
  try {
    prompt.value = await api.getPrompt(promptId.value)
    const versionId = prompt.value.current_version_id || prompt.value.versions[0]?.id
    if (versionId) {
      currentVersion.value = await api.getVersion(promptId.value, versionId)
    }
  } finally {
    loading.value = false
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'full' && prompt.value && prompt.value.current_version_id) {
    try {
      renderedMessages.value = []
      const versionId = currentVersion.value?.id || prompt.value.current_version_id
      const result = await api.previewPrompt(promptId.value, versionId)
      renderedMessages.value = result.messages || []
    } catch { }
  }
})

function statusType(status: string) {
  const map: Record<string, string> = {
    draft: 'info', testing: 'warning', reviewing: 'warning',
    approved: 'success', rejected: 'danger', gray: 'warning',
    published: 'success', offline: 'info', archived: 'info',
  }
  return map[status] || 'info'
}

async function previewVersion(versionId: number) {
  try {
    const version = await api.getVersion(promptId.value, versionId)
    currentVersion.value = version
    renderedMessages.value = []
    const result = await api.previewPrompt(promptId.value, versionId)
    renderedMessages.value = result.messages || []
    activeTab.value = 'full'
  } catch { }
}

function compareWith(versionId: number) {
  router.push(`/prompt-center/${promptId.value}/compare?target=${versionId}`)
}

async function reloadPrompt() {
  prompt.value = await api.getPrompt(promptId.value)
  const versionId = prompt.value.current_version_id || prompt.value.versions[0]?.id
  currentVersion.value = versionId
    ? await api.getVersion(promptId.value, versionId)
    : null
}

async function submitReview(versionId: number) {
  await api.submitVersion(promptId.value, versionId)
  ElMessage.success('已提交审核')
  await reloadPrompt()
}

async function approveReview(versionId: number) {
  await api.approveVersion(promptId.value, versionId)
  ElMessage.success('审核通过')
  await reloadPrompt()
}

async function rejectReview(versionId: number) {
  try {
    await ElMessageBox.confirm('确认驳回该版本？', '审核确认')
  } catch {
    return
  }
  await api.rejectVersion(promptId.value, versionId)
  ElMessage.success('版本已驳回')
  await reloadPrompt()
}
</script>

<style scoped>
.prompt-detail { padding: 24px; }
.page-header { margin-bottom: 24px; }
.section-card { margin-top: 16px; }
.section { margin-bottom: 16px; }
.section h4 { margin: 0 0 8px; color: #606266; }
.section pre { background: #f5f7fa; padding: 12px; border-radius: 4px; white-space: pre-wrap; font-size: 13px; line-height: 1.6; }
.strikethrough { text-decoration: line-through; color: #c0c4cc; }
.message-block { margin-bottom: 16px; border: 1px solid #ebeef5; border-radius: 4px; }
.message-role { background: #f5f7fa; padding: 8px 12px; font-weight: 600; font-size: 13px; border-bottom: 1px solid #ebeef5; }
.message-content { padding: 12px; margin: 0; white-space: pre-wrap; font-size: 13px; line-height: 1.6; }
.version-item { display: flex; align-items: center; gap: 8px; }
.version-actions { margin-left: auto; }
</style>
