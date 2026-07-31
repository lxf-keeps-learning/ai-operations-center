<template>
  <div class="quality-page" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/prompt-center' }">Prompt 管理</el-breadcrumb-item>
        <el-breadcrumb-item>质量评估</el-breadcrumb-item>
      </el-breadcrumb>
      <div class="header-actions">
        <el-input
          v-model="promptKey"
          placeholder="输入 Prompt Key 查询，如 ioc.safety.analysis"
          style="width: 360px"
          clearable
          @keyup.enter="loadData"
        />
        <el-button type="primary" @click="loadData" :disabled="!promptKey">查询</el-button>
      </div>
    </div>

    <template v-if="metrics">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card shadow="never">
            <div class="metric-card">
              <div class="metric-label">Prompt 遵守率</div>
              <div class="metric-value" :class="scoreColor(metrics.compliance_rate)">{{ metrics.compliance_rate }}%</div>
              <div class="metric-sub">基于 {{ metrics.total_evaluations }} 次评估</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never">
            <div class="metric-card">
              <div class="metric-label">格式合规率</div>
              <div class="metric-value" :class="scoreColor(metrics.format_compliance)">{{ metrics.format_compliance }}%</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never">
            <div class="metric-card">
              <div class="metric-label">虚构率</div>
              <div class="metric-value" :class="inverseScoreColor(metrics.hallucination_rate)">{{ metrics.hallucination_rate }}%</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never">
            <div class="metric-card">
              <div class="metric-label">证据完整率</div>
              <div class="metric-value" :class="scoreColor(metrics.evidence_complete_rate)">{{ metrics.evidence_complete_rate }}%</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span>评估趋势（近 7 天）</span></template>
            <div v-if="trends.length" class="trend-chart">
              <div v-for="(item, i) in trendsByDate" :key="i" class="trend-bar-group">
                <div class="trend-date">{{ item.date.slice(5) }}</div>
                <div class="trend-bars">
                  <div
                    v-for="t in item.items" :key="t.evaluator_key"
                    class="trend-bar"
                    :style="{ height: t.avg_score * 60 + 'px', background: barColor(t.evaluator_key) }"
                    :title="`${EVALUATOR_KEY_MAP[t.evaluator_key] || t.evaluator_key}: ${(t.avg_score * 100).toFixed(0)}%`"
                  />
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无趋势数据" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span>失败原因分布</span></template>
            <div v-if="failures.length">
              <div v-for="f in failures" :key="f.evaluator_key" class="failure-row">
                <span class="failure-key">{{ EVALUATOR_KEY_MAP[f.evaluator_key] || f.evaluator_key }}</span>
                <el-progress
                  :percentage="failurePercent(f.failure_count)"
                  :stroke-width="18"
                  :color="failureColor(f.evaluator_key)"
                >
                  <span class="failure-count">{{ f.failure_count }} 次</span>
                </el-progress>
              </div>
            </div>
            <el-empty v-else description="暂无失败记录" />
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-top: 16px">
        <template #header>
          <div class="card-header">
            <span>评估结果明细</span>
            <div class="card-header-actions">
              <el-select v-model="filterEvaluator" placeholder="筛选评估器" clearable style="width: 160px" @change="loadResults">
                <el-option v-for="e in evaluators" :key="e.key" :label="e.name" :value="e.key" />
              </el-select>
              <el-select v-model="filterPassed" placeholder="筛选结果" clearable style="width: 120px; margin-left: 8px" @change="loadResults">
                <el-option label="通过" :value="true" />
                <el-option label="未通过" :value="false" />
              </el-select>
            </div>
          </div>
        </template>
        <el-table :data="results" stripe size="small" v-loading="resultsLoading" max-height="500">
          <el-table-column prop="evaluator_key" label="评估器" width="140">
            <template #default="{ row }">
              <el-tag size="small">{{ EVALUATOR_KEY_MAP[row.evaluator_key] || row.evaluator_key }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="evaluator_type" label="类型" width="100">
            <template #default="{ row }">
              {{ EVALUATOR_TYPE_MAP[row.evaluator_type] || row.evaluator_type }}
            </template>
          </el-table-column>
          <el-table-column label="结果" width="80">
            <template #default="{ row }">
              <el-tag :type="row.passed ? 'success' : 'danger'" size="small">{{ row.passed ? '通过' : '未通过' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="score" label="评分" width="80">
            <template #default="{ row }">
              {{ row.score != null ? (row.score * 100).toFixed(0) + '%' : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="说明" min-width="300" show-overflow-tooltip />
          <el-table-column prop="created_at" label="时间" width="170" />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="showDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination" v-if="resultsTotal > 20">
          <el-pagination
            v-model:current-page="resultsPage"
            :page-size="20"
            :total="resultsTotal"
            layout="total, prev, pager, next"
            @current-change="loadResults"
            small
          />
        </div>
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="请输入 Prompt Key 查询质量指标" />

    <el-dialog v-model="detailVisible" title="评估详情" width="700px">
      <template v-if="currentDetail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="评估器">{{ EVALUATOR_KEY_MAP[currentDetail.evaluator_key] || currentDetail.evaluator_key }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ EVALUATOR_TYPE_MAP[currentDetail.evaluator_type] }}</el-descriptions-item>
          <el-descriptions-item label="结果">
            <el-tag :type="currentDetail.passed ? 'success' : 'danger'" size="small">{{ currentDetail.passed ? '通过' : '未通过' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="评分">{{ currentDetail.score != null ? (currentDetail.score * 100).toFixed(0) + '%' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="Prompt Key">{{ currentDetail.prompt_key }}</el-descriptions-item>
          <el-descriptions-item label="Trace ID">{{ currentDetail.trace_id }}</el-descriptions-item>
        </el-descriptions>
        <div style="margin-top: 16px">
          <h4>评估说明</h4>
          <p>{{ currentDetail.reason || '无' }}</p>
        </div>
        <div v-if="currentDetail.violations?.length" style="margin-top: 12px">
          <h4>违规项</h4>
          <ul>
            <li v-for="(v, i) in currentDetail.violations" :key="i" class="violation-item">{{ v }}</li>
          </ul>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { EVALUATOR_KEY_MAP, EVALUATOR_TYPE_MAP } from '@/types/evaluation-center'
import * as api from '@/api/evaluation-center'
import type { EvaluationMetrics, EvaluationResult, TrendItem, FailureItem, EvaluatorInfo } from '@/types/evaluation-center'

const loading = ref(false)
const resultsLoading = ref(false)
const promptKey = ref('ioc.safety.analysis')
const metrics = ref<EvaluationMetrics | null>(null)
const trends = ref<TrendItem[]>([])
const failures = ref<FailureItem[]>([])
const evaluators = ref<EvaluatorInfo[]>([])
const results = ref<EvaluationResult[]>([])
const resultsTotal = ref(0)
const resultsPage = ref(1)
const filterEvaluator = ref('')
const filterPassed = ref<boolean | ''>('')
const detailVisible = ref(false)
const currentDetail = ref<EvaluationResult | null>(null)

const trendsByDate = computed(() => {
  const map = new Map<string, TrendItem[]>()
  for (const t of trends.value) {
    if (!map.has(t.date)) map.set(t.date, [])
    map.get(t.date)!.push(t)
  }
  return Array.from(map.entries()).map(([date, items]) => ({ date, items }))
})

onMounted(() => {
  loadData()
  api.listEvaluators().then(e => evaluators.value = e).catch(() => {})
})

async function loadData() {
  if (!promptKey.value) return
  loading.value = true
  try {
    const [m, t, f] = await Promise.all([
      api.getPromptMetrics(promptKey.value),
      api.getPromptTrends(promptKey.value),
      api.getPromptFailures(promptKey.value),
    ])
    metrics.value = m
    trends.value = t
    failures.value = f
    loadResults()
  } catch {
    metrics.value = null
    trends.value = []
    failures.value = []
  } finally {
    loading.value = false
  }
}

async function loadResults() {
  if (!promptKey.value) return
  resultsLoading.value = true
  try {
    const result = await api.listResults(promptKey.value, {
      page: resultsPage.value,
      page_size: 20,
      evaluator_key: filterEvaluator.value || undefined,
      passed: filterPassed.value !== '' ? filterPassed.value as boolean : undefined,
    })
    results.value = result.items
    resultsTotal.value = result.total
  } catch {
    results.value = []
    resultsTotal.value = 0
  } finally {
    resultsLoading.value = false
  }
}

function scoreColor(val: number) {
  if (val >= 80) return 'score-green'
  if (val >= 60) return 'score-yellow'
  return 'score-red'
}

function inverseScoreColor(val: number) {
  if (val <= 10) return 'score-green'
  if (val <= 30) return 'score-yellow'
  return 'score-red'
}

function barColor(key: string) {
  const colors: Record<string, string> = {
    json_format: '#409eff',
    field_completeness: '#67c23a',
    enum_check: '#e6a23c',
    no_hallucination: '#f56c6c',
    evidence_provided: '#909399',
    question_answered: '#409eff',
    data_grounded: '#67c23a',
    actionable_advice: '#e6a23c',
  }
  return colors[key] || '#409eff'
}

function failureColor(key: string) {
  const colors: Record<string, string> = {
    no_hallucination: '#f56c6c',
    json_format: '#409eff',
    field_completeness: '#67c23a',
    question_answered: '#409eff',
  }
  return colors[key] || '#909399'
}

function failurePercent(count: number) {
  const max = Math.max(...failures.value.map(f => f.failure_count), 1)
  return Math.round((count / max) * 100)
}

function showDetail(row: EvaluationResult) {
  currentDetail.value = row
  detailVisible.value = true
}
</script>

<style scoped>
.quality-page { padding: 24px; }
.page-header { margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.metric-card { text-align: center; padding: 8px 0; }
.metric-label { font-size: 14px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 28px; font-weight: 700; }
.metric-sub { font-size: 12px; color: #c0c4cc; margin-top: 4px; }
.score-green { color: #67c23a; }
.score-yellow { color: #e6a23c; }
.score-red { color: #f56c6c; }
.trend-chart { display: flex; align-items: flex-end; gap: 8px; height: 100px; padding: 12px 0; }
.trend-bar-group { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.trend-bars { display: flex; gap: 3px; align-items: flex-end; height: 70px; }
.trend-bar { width: 12px; border-radius: 3px 3px 0 0; min-height: 4px; transition: height 0.3s; }
.trend-date { font-size: 11px; color: #909399; }
.failure-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.failure-key { min-width: 100px; font-size: 13px; color: #606266; }
.failure-count { font-size: 12px; color: #fff; padding: 0 8px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header-actions { display: flex; }
.pagination { margin-top: 12px; display: flex; justify-content: flex-end; }
.violation-item { color: #f56c6c; font-size: 13px; margin-bottom: 4px; }
</style>
