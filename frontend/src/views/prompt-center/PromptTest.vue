<template>
  <div class="prompt-test" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/prompt-center' }">Prompt 管理</el-breadcrumb-item>
        <el-breadcrumb-item :to="{ path: `/prompt-center/${promptId}` }">{{ prompt?.prompt_name || '测试' }}</el-breadcrumb-item>
        <el-breadcrumb-item>测试调优</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <el-form :model="testForm" label-width="100px">
      <el-form-item label="测试版本">
        <el-select v-model="testForm.versionId" placeholder="选择版本">
          <el-option v-for="v in versions" :key="v.id" :label="`v${v.version} (${statusMap[v.status]})`" :value="v.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="测试输入">
        <div class="test-case-info" v-if="selectedCase">
          <el-tag>{{ selectedCase.case_name }}</el-tag>
          <el-button link type="primary" @click="selectedCase = null">清除</el-button>
        </div>
        <div class="input-editor">
          <el-input
            v-model="testForm.userQuestion"
            placeholder="用户问题"
            style="margin-bottom: 8px"
          />
          <div v-for="(_, key) in testForm.variables" :key="key" class="var-row">
            <span class="var-label">{{ key }}</span>
            <el-input v-model="testForm.variables[key]" :placeholder="key" />
          </div>
        </div>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="runSingleTest" :loading="testing">运行测试</el-button>
        <el-button @click="loadPresetCases">加载预置用例</el-button>
      </el-form-item>
    </el-form>

    <div v-if="testResult" class="test-result">
      <el-tabs v-model="resultTab">
        <el-tab-pane label="测试结果" name="output">
          <el-card>
            <template #header>
              <div class="result-header">
                <span>模型输出</span>
                <el-tag :type="testResult.status === 'completed' ? 'success' : 'danger'" size="small">
                  {{ testResult.status === 'completed' ? '成功' : '失败' }}
                </el-tag>
                <span class="result-meta" v-if="testResult.latency">{{ testResult.latency }}ms</span>
              </div>
            </template>
            <pre class="output-content">{{ testResult.raw_output || '（无输出）' }}</pre>
          </el-card>

          <el-card class="section-card" v-if="testResult.structured_output">
            <template #header><span>结构化输出</span></template>
            <pre class="json-content">{{ JSON.stringify(testResult.structured_output, null, 2) }}</pre>
          </el-card>

          <el-card class="section-card" v-if="testResult.token_usage">
            <template #header><span>Token 使用</span></template>
            <el-descriptions :column="3" size="small">
              <el-descriptions-item label="输入 Token">{{ testResult.token_usage.input_tokens }}</el-descriptions-item>
              <el-descriptions-item label="输出 Token">{{ testResult.token_usage.output_tokens }}</el-descriptions-item>
              <el-descriptions-item label="总计">{{ testResult.token_usage.total_tokens }}</el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card class="section-card" v-if="testResult.rendered_prompt">
            <template #header><span>最终 Prompt</span></template>
            <pre class="output-content">{{ testResult.rendered_prompt }}</pre>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="评估结果" name="evaluation">
          <el-card v-if="evalSummary">
            <template #header>
              <span>遵守率: {{ evalSummary.compliance_rate }}% ({{ evalSummary.passed_checks }}/{{ evalSummary.total_checks }})</span>
            </template>
            <el-table :data="evalSummary.evaluations" stripe size="small">
              <el-table-column prop="evaluator_key" label="评估项" width="180" />
              <el-table-column prop="evaluator_type" label="类型" width="120" />
              <el-table-column label="结果" width="80">
                <template #default="{ row }">
                  <el-tag :type="row.passed ? 'success' : 'danger'" size="small">{{ row.passed ? '通过' : '未通过' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="score" label="评分" width="80" />
              <el-table-column prop="reason" label="说明" />
            </el-table>
          </el-card>
          <el-empty v-else description="暂无评估结果" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="presetDialogVisible" title="选择预置测试用例" width="600px">
      <el-table :data="testCases" stripe @row-click="selectPresetCase">
        <el-table-column prop="case_name" label="用例名称" />
        <el-table-column prop="case_type" label="类型" width="100" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="selectPresetCase(row)">选择</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { PROMPT_STATUS_MAP } from '@/types/prompt-center'
import * as api from '@/api/prompt-center'
import type { PromptDetail, PromptVersionSummary, TestCase, TestRun, EvaluationSummary } from '@/types/prompt-center'

const route = useRoute()
const promptId = computed(() => Number(route.params.id))
const loading = ref(false)
const testing = ref(false)
const prompt = ref<PromptDetail | null>(null)
const versions = ref<PromptVersionSummary[]>([])
const testCases = ref<TestCase[]>([])
const testResult = ref<TestRun | null>(null)
const evalSummary = ref<EvaluationSummary | null>(null)
const selectedCase = ref<TestCase | null>(null)
const resultTab = ref('output')
const presetDialogVisible = ref(false)
const statusMap = PROMPT_STATUS_MAP

const testForm = reactive({
  versionId: null as number | null,
  userQuestion: '',
  variables: {} as Record<string, string>,
})

onMounted(async () => {
  loading.value = true
  try {
    prompt.value = await api.getPrompt(promptId.value)
    versions.value = prompt.value.versions
    testForm.variables = Object.fromEntries(
      prompt.value.variables
        .filter(variable => variable.variable_key !== 'user_question')
        .map(variable => [
          variable.variable_key,
          variable.example_value || variable.default_value || '',
        ]),
    )
    if (versions.value.length) {
      testForm.versionId = versions.value[0].id
    }
  } finally {
    loading.value = false
  }
})

async function runSingleTest() {
  if (!testForm.versionId) {
    ElMessage.warning('请选择测试版本')
    return
  }
  testing.value = true
  try {
    testResult.value = await api.runTest(promptId.value, testForm.versionId, {
      user_question: testForm.userQuestion,
      ...testForm.variables,
    })
    if (testResult.value.id) {
      try {
        evalSummary.value = await api.getTestRunEvaluation(testResult.value.id)
      } catch { }
    }
    resultTab.value = 'output'
  } catch (e: any) {
    ElMessage.error(e.message || '测试失败')
  } finally {
    testing.value = false
  }
}

async function loadPresetCases() {
  try {
    testCases.value = await api.listTestCases(promptId.value)
    presetDialogVisible.value = true
  } catch {
    ElMessage.info('暂无预置测试用例')
  }
}

function selectPresetCase(case_: TestCase) {
  selectedCase.value = case_
  testForm.variables = {}
  for (const [key, val] of Object.entries(case_.input_data)) {
    if (key === 'user_question') {
      testForm.userQuestion = String(val || '')
    } else {
      testForm.variables[key] = typeof val === 'object' ? JSON.stringify(val) : String(val || '')
    }
  }
  presetDialogVisible.value = false
}
</script>

<style scoped>
.prompt-test { padding: 24px; }
.page-header { margin-bottom: 24px; }
.test-case-info { margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.var-row { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.var-label { font-size: 13px; color: #606266; min-width: 120px; }
.test-result { margin-top: 24px; }
.section-card { margin-top: 16px; }
.result-header { display: flex; align-items: center; gap: 12px; }
.result-meta { color: #909399; font-size: 13px; }
.output-content, .json-content { margin: 0; white-space: pre-wrap; font-size: 13px; line-height: 1.5; }
</style>
