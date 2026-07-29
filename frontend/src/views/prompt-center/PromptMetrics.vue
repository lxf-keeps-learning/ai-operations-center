<template>
  <div class="prompt-metrics" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/prompt-center' }">Prompt 管理</el-breadcrumb-item>
        <el-breadcrumb-item :to="{ path: `/prompt-center/${promptId}` }">{{ prompt?.prompt_name || '指标' }}</el-breadcrumb-item>
        <el-breadcrumb-item>运行指标</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <el-row :gutter="16">
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">Prompt 遵守率</div>
            <div class="metric-value">{{ metrics?.compliance_rate ?? '-' }}{{ metrics?.compliance_rate != null ? '%' : '' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">JSON 格式通过率</div>
            <div class="metric-value">{{ metrics?.format_compliance ?? '-' }}{{ metrics?.format_compliance != null ? '%' : '' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">平均 Token</div>
            <div class="metric-value">{{ metrics?.avg_tokens ?? '-' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">平均响应时间</div>
            <div class="metric-value">{{ metrics?.avg_latency_ms ?? '-' }}ms</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">无虚构率</div>
            <div class="metric-value">{{ metrics?.no_fabrication_rate ?? '-' }}{{ metrics?.no_fabrication_rate != null ? '%' : '' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">证据完整率</div>
            <div class="metric-value">{{ metrics?.evidence_complete_rate ?? '-' }}{{ metrics?.evidence_complete_rate != null ? '%' : '' }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">总运行次数</div>
            <div class="metric-value">{{ metrics?.total_runs ?? 0 }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="metric-card">
            <div class="metric-label">失败次数</div>
            <div class="metric-value">{{ metrics?.total_failures ?? 0 }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="section-card">
      <template #header><span>测试运行记录</span></template>
      <el-table :data="testRuns" stripe size="small" v-if="testRuns.length" max-height="400">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="model_name" label="模型" width="140" />
        <el-table-column prop="latency" label="耗时 (ms)" width="100" />
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewTestRun(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无测试记录" />
    </el-card>

    <el-dialog v-model="runDetailVisible" title="测试详情" width="800px">
      <template v-if="currentRun">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="状态">
            <el-tag :type="currentRun.status === 'completed' ? 'success' : 'danger'" size="small">{{ currentRun.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="模型">{{ currentRun.model_name }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ currentRun.latency }}ms</el-descriptions-item>
          <el-descriptions-item label="Trace ID">{{ currentRun.trace_id || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="currentRun.raw_output" style="margin-top: 16px">
          <h4>模型输出</h4>
          <pre class="output-content">{{ currentRun.raw_output }}</pre>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import * as api from '@/api/prompt-center'
import type { PromptDetail, PromptMetrics, TestRun } from '@/types/prompt-center'

const route = useRoute()
const promptId = computed(() => Number(route.params.id))
const loading = ref(false)
const prompt = ref<PromptDetail | null>(null)
const metrics = ref<PromptMetrics | null>(null)
const testRuns = ref<TestRun[]>([])
const currentRun = ref<TestRun | null>(null)
const runDetailVisible = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    prompt.value = await api.getPrompt(promptId.value)
    metrics.value = await api.getPromptMetrics(promptId.value)
    testRuns.value = await api.listTestRuns(promptId.value, 1, 20)
  } finally {
    loading.value = false
  }
})

function viewTestRun(runId: number) {
  api.getTestRun(runId).then(run => {
    currentRun.value = run
    runDetailVisible.value = true
  })
}
</script>

<style scoped>
.prompt-metrics { padding: 24px; }
.page-header { margin-bottom: 24px; }
.section-card { margin-top: 16px; }
.metric-card { text-align: center; padding: 8px 0; }
.metric-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 28px; font-weight: 700; color: #303133; }
.output-content { margin: 0; padding: 12px; background: #f5f7fa; border-radius: 4px; white-space: pre-wrap; font-size: 13px; max-height: 400px; overflow-y: auto; }
</style>
