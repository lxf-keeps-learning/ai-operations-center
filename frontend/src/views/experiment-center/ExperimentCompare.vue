<template>
  <div class="exp-compare" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/experiments' }">实验中心</el-breadcrumb-item>
        <el-breadcrumb-item>版本对比</el-breadcrumb-item>
      </el-breadcrumb>
      <h1>{{ compare?.experiment_name || '版本对比' }}</h1>
    </div>

    <template v-if="compare">
      <el-alert
        :title="winnerTitle"
        :type="winnerType"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      />

      <el-row :gutter="16">
        <el-col :span="8">
          <el-card shadow="never">
            <div class="metric-card">
              <div class="metric-label">版本</div>
              <div class="metric-value">
                <el-tag size="small">v{{ compare.source_version.version }}</el-tag>
                <span style="margin: 0 8px;color:#909399">vs</span>
                <el-tag size="small" type="warning">v{{ compare.target_version.version }}</el-tag>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never">
            <div class="metric-card">
              <div class="metric-label">平均 Token</div>
              <div class="metric-value">
                <span>{{ compare.source_version.avg_tokens }}</span>
                <span style="margin: 0 8px;color:#909399">→</span>
                <span>{{ compare.target_version.avg_tokens }}</span>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never">
            <div class="metric-card">
              <div class="metric-label">平均延迟</div>
              <div class="metric-value">
                <span>{{ compare.source_version.avg_latency_ms }}ms</span>
                <span style="margin: 0 8px;color:#909399">→</span>
                <span>{{ compare.target_version.avg_latency_ms }}ms</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-top: 16px">
        <template #header><span>指标对比</span></template>
        <el-table :data="compare.metric_comparisons" stripe size="small">
          <el-table-column label="指标" min-width="160">
            <template #default="{ row }">
              <span class="metric-key">{{ METRIC_LABELS[row.metric_key] || row.metric_key }}</span>
            </template>
          </el-table-column>
          <el-table-column label="源版本" width="120" align="center">
            <template #default="{ row }">
              <span :class="row.source_score >= 0.8 ? 'score-good' : row.source_score >= 0.5 ? 'score-ok' : 'score-bad'">
                {{ (row.source_score * 100).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="目标版本" width="120" align="center">
            <template #default="{ row }">
              <span :class="row.target_score >= 0.8 ? 'score-good' : row.target_score >= 0.5 ? 'score-ok' : 'score-bad'">
                {{ (row.target_score * 100).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="差异" width="120" align="center">
            <template #default="{ row }">
              <el-tag :type="row.diff > 0 ? 'success' : row.diff < 0 ? 'danger' : 'info'" size="small">
                {{ row.diff > 0 ? '+' : '' }}{{ (row.diff * 100).toFixed(1) }}%
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="较优版本" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.better === 'source'" type="success" size="small">源版本</el-tag>
              <el-tag v-else-if="row.better === 'target'" type="warning" size="small">目标版本</el-tag>
              <el-tag v-else size="small">持平</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" style="margin-top: 16px">
        <template #header>
          <div class="card-header">
            <span>详细结果</span>
            <el-radio-group v-model="resultVersion" size="small">
              <el-radio value="">全部</el-radio>
              <el-radio value="source">源版本</el-radio>
              <el-radio value="target">目标版本</el-radio>
            </el-radio-group>
          </div>
        </template>
        <el-table :data="filteredResults" stripe size="small" max-height="500">
          <el-table-column label="版本" width="80">
            <template #default="{ row }">
              <el-tag :type="row.version === 'source' ? 'success' : 'warning'" size="small">{{ row.version }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'completed' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="latency_ms" label="延迟(ms)" width="90" />
          <el-table-column label="Token" width="120">
            <template #default="{ row }">{{ row.token_usage?.total_tokens || '-' }}</template>
          </el-table-column>
          <el-table-column label="输出预览" min-width="300">
            <template #default="{ row }">
              <div class="output-preview">{{ (row.raw_output || '').slice(0, 200) }}{{ (row.raw_output || '').length > 200 ? '...' : '' }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as api from '@/api/experiment-center'
import type { CompareResult, ExperimentResultRow } from '@/types/experiment-center'

const route = useRoute()
const loading = ref(false)
const experimentId = computed(() => Number(route.params.id))
const compare = ref<CompareResult | null>(null)
const allResults = ref<ExperimentResultRow[]>([])
const resultVersion = ref('')

const METRIC_LABELS: Record<string, string> = {
  json_format: 'JSON 格式',
  field_completeness: '字段完整性',
  enum_check: '枚举值检查',
  response_length: '响应长度',
  question_answered: '回答问题',
  data_grounded: '基于数据',
  no_hallucination: '虚构率',
  evidence_provided: '提供依据',
  actionable_advice: '可执行建议',
}

const filteredResults = computed(() => {
  if (!resultVersion.value) return allResults.value
  return allResults.value.filter(r => r.version === resultVersion.value)
})

const winnerTitle = computed(() => {
  if (!compare.value) return ''
  const w = compare.value.winner
  if (w === 'source') return '源版本表现更优'
  if (w === 'target') return '目标版本表现更优'
  if (w === 'draw') return '两个版本表现接近'
  return '结果待定'
})

const winnerType = computed(() => {
  if (!compare.value) return 'info'
  const w = compare.value.winner
  if (w === 'source') return 'success'
  if (w === 'target') return 'warning'
  if (w === 'draw') return 'info'
  return 'info'
})

onMounted(async () => {
  loading.value = true
  try {
    const [c, results] = await Promise.all([
      api.compareExperiment(experimentId.value),
      api.getExperimentResults(experimentId.value),
    ])
    compare.value = c
    allResults.value = results
  } finally {
    loading.value = false
  }
})

watch(resultVersion, async (v) => {
  allResults.value = await api.getExperimentResults(experimentId.value, v || undefined)
})
</script>

<style scoped>
.exp-compare { padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 12px 0 0; font-size: 22px; }
.metric-card { text-align: center; padding: 12px 0; }
.metric-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 20px; font-weight: 600; }
.score-good { color: #67c23a; font-weight: 600; }
.score-ok { color: #e6a23c; font-weight: 600; }
.score-bad { color: #f56c6c; font-weight: 600; }
.metric-key { font-size: 14px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.output-preview { font-size: 12px; color: #606266; line-height: 1.4; max-height: 60px; overflow: hidden; }
</style>
