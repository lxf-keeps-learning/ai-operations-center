<template>
  <div class="failure-detail" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/failures' }">失败案例</el-breadcrumb-item>
        <el-breadcrumb-item>案例 #{{ failureId }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <template v-if="detail">
      <el-alert :title="`${TYPE_LABELS[detail.failure_type] || detail.failure_type}`" :type="alertType" show-icon :closable="false" style="margin-bottom: 16px">
        <template #default>
          <p>{{ detail.reason }}</p>
        </template>
      </el-alert>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span>基本信息</span></template>
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="Prompt Key">{{ detail.prompt_key || '-' }}</el-descriptions-item>
              <el-descriptions-item label="版本">{{ detail.prompt_version || '-' }}</el-descriptions-item>
              <el-descriptions-item label="Trace ID">{{ detail.trace_id || '-' }}</el-descriptions-item>
              <el-descriptions-item label="Graph">{{ detail.graph_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="严重程度">
                <el-tag :type="SEVERITY_MAP[detail.severity]?.type" size="small">{{ SEVERITY_MAP[detail.severity]?.label }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                <el-tag :type="STATUS_MAP[detail.status]?.type" size="small">{{ STATUS_MAP[detail.status]?.label }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="评估分" v-if="detail.eval_score != null">{{ (detail.eval_score * 100).toFixed(1) }}%</el-descriptions-item>
              <el-descriptions-item label="创建于">{{ detail.created_at }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card shadow="never">
            <template #header>
              <div class="card-header"><span>操作</span></div>
            </template>
            <div class="action-buttons">
              <el-button v-if="detail.status === 'pending'" type="success" @click="doConvert" :loading="converting">生成测试用例</el-button>
              <el-button v-if="detail.status === 'pending'" type="warning" @click="startAnalyze">分析</el-button>
              <el-button v-if="detail.generated_case_id" type="info" @click="gotoTestCase">查看测试用例 #{{ detail.generated_case_id }}</el-button>
            </div>
            <div v-if="detail.generated_case_id" style="margin-top: 12px">
              <el-alert title="已转换为测试用例" type="success" show-icon :closable="false" />
            </div>
          </el-card>

          <el-card shadow="never" style="margin-top: 12px">
            <template #header><span>分析</span></template>
            <div v-if="detail.analysis">
              <pre class="analysis-content">{{ detail.analysis }}</pre>
            </div>
            <div v-else class="no-analysis">
              <el-button type="primary" @click="startAnalyze">添加分析</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" style="margin-top: 16px">
        <template #header><span>关联评估结果</span></template>
        <el-table v-if="detail.eval_results?.length" :data="detail.eval_results" stripe size="small">
          <el-table-column prop="evaluator_key" label="评估器" width="160" />
          <el-table-column label="结果" width="80">
            <template #default="{ row }">
              <el-tag :type="row.passed ? 'success' : 'danger'" size="small">{{ row.passed ? '通过' : '未通过' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="score" label="评分" width="80">
            <template #default="{ row }">{{ row.score != null ? (row.score * 100).toFixed(0) + '%' : '-' }}</template>
          </el-table-column>
          <el-table-column prop="reason" label="说明" />
        </el-table>
        <el-empty v-else description="无关联评估结果" />
      </el-card>
    </template>

    <el-dialog v-model="analyzeVisible" title="分析失败案例" width="600px">
      <el-input v-model="analyzeText" type="textarea" :rows="6" placeholder="分析失败原因、改善建议..." />
      <template #footer>
        <el-button @click="analyzeVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAnalyze" :loading="analyzing">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { FAILURE_TYPE_LABELS, SEVERITY_MAP, STATUS_MAP } from '@/types/failure-center'
import * as api from '@/api/failure-center'
import type { FailureDetail } from '@/types/failure-center'

const route = useRoute()
const failureId = computed(() => Number(route.params.id))
const loading = ref(false)
const converting = ref(false)
const analyzing = ref(false)
const detail = ref<FailureDetail | null>(null)
const analyzeVisible = ref(false)
const analyzeText = ref('')
const TYPE_LABELS = FAILURE_TYPE_LABELS

const alertType = computed(() => {
  const s = detail.value?.severity
  if (s === 'critical') return 'error'
  if (s === 'high') return 'warning'
  return 'info'
})

onMounted(async () => {
  loading.value = true
  try {
    detail.value = await api.getFailure(failureId.value)
  } finally {
    loading.value = false
  }
})

async function doConvert() {
  converting.value = true
  try {
    detail.value = await api.convertFailure(failureId.value)
    ElMessage.success('已生成测试用例')
  } catch (e: any) {
    ElMessage.error(e.message || '转化失败')
  } finally {
    converting.value = false
  }
}

function startAnalyze() {
  analyzeText.value = detail.value?.analysis || ''
  analyzeVisible.value = true
}

async function saveAnalyze() {
  analyzing.value = true
  try {
    detail.value = await api.analyzeFailure(failureId.value, analyzeText.value)
    ElMessage.success('分析已保存')
    analyzeVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    analyzing.value = false
  }
}

function gotoTestCase() {
  if (detail.value?.generated_case_id) {
    ElMessage.info('测试用例 ID: ' + detail.value.generated_case_id)
  }
}
</script>

<style scoped>
.failure-detail { padding: 24px; }
.page-header { margin-bottom: 24px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.action-buttons { display: flex; gap: 8px; flex-wrap: wrap; }
.analysis-content { margin: 0; white-space: pre-wrap; font-size: 13px; line-height: 1.6; background: #f5f7fa; padding: 12px; border-radius: 4px; }
.no-analysis { text-align: center; padding: 24px; color: #909399; }
</style>
