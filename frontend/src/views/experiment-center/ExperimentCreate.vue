<template>
  <div class="exp-create" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/experiments' }">实验中心</el-breadcrumb-item>
        <el-breadcrumb-item>创建实验</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <el-card style="max-width: 800px">
      <template #header><span>实验配置</span></template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="实验名称" required>
          <el-input v-model="form.name" placeholder="例：安全分析 V1 vs V2 对比" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="Prompt" required>
          <el-select v-model="form.prompt_id" filterable placeholder="选择 Prompt" @change="onPromptChange" style="width: 100%">
            <el-option v-for="p in prompts" :key="p.id" :label="`${p.prompt_name} (${p.prompt_key})`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="源版本" required>
          <el-select v-model="form.source_version_id" placeholder="选择源版本" @change="updateVersionLabels">
            <el-option v-for="v in versions" :key="v.id" :label="`v${v.version} (${v.status})`" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标版本" required>
          <el-select v-model="form.target_version_id" placeholder="选择目标版本" @change="updateVersionLabels">
            <el-option v-for="v in versions" :key="v.id" :label="`v${v.version} (${v.status})`" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="测试数据集" required>
          <el-table :data="testCases" stripe size="small" max-height="300" @selection-change="onSelectionChange">
            <el-table-column type="selection" width="40" />
            <el-table-column prop="case_name" label="用例名称" />
            <el-table-column label="选中" width="80">
              <template #default="{ row }">
                <el-tag v-if="selectedIds.has(row.id)" type="success" size="small">已选</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 8px; color: #909399; font-size: 13px">已选 {{ selectedIds.size }} 个测试用例</div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createAndRun" :loading="creating" :disabled="!canSubmit">创建并运行</el-button>
          <el-button @click="router.push('/experiments')">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as api from '@/api/experiment-center'
import * as promptApi from '@/api/prompt-center'
import type { PromptDefinition, PromptVersionSummary, TestCase } from '@/types/prompt-center'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const prompts = ref<PromptDefinition[]>([])
const versions = ref<PromptVersionSummary[]>([])
const testCases = ref<TestCase[]>([])
const selectedIds = ref<Set<number>>(new Set())

const form = reactive({
  name: '',
  description: '',
  prompt_id: null as number | null,
  source_version_id: null as number | null,
  target_version_id: null as number | null,
  test_case_ids: [] as number[],
})

const canSubmit = computed(() => form.name && form.prompt_id && form.source_version_id && form.target_version_id && selectedIds.value.size > 0)

onMounted(async () => {
  loading.value = true
  try {
    const result = await promptApi.listPrompts()
    prompts.value = result.items as any as PromptDefinition[]
  } finally {
    loading.value = false
  }
})

async function onPromptChange(promptId: number) {
  form.source_version_id = null
  form.target_version_id = null
  versions.value = []
  testCases.value = []
  try {
    versions.value = await promptApi.listVersions(promptId)
    testCases.value = await promptApi.listTestCases(promptId)
  } catch { }
}

function updateVersionLabels() {}

function onSelectionChange(rows: TestCase[]) {
  selectedIds.value = new Set(rows.map(r => r.id))
  form.test_case_ids = Array.from(selectedIds.value)
}

async function createAndRun() {
  if (!canSubmit.value) return
  creating.value = true
  try {
    const exp = await api.createExperiment({
      name: form.name,
      description: form.description || undefined,
      prompt_id: form.prompt_id!,
      source_version_id: form.source_version_id!,
      target_version_id: form.target_version_id!,
      test_case_ids: form.test_case_ids,
    })
    ElMessage.success('实验创建成功，开始运行...')
    await api.runExperiment(exp.id)
    ElMessage.success('实验运行完成')
    router.push(`/experiments/${exp.id}/compare`)
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.exp-create { padding: 24px; }
.page-header { margin-bottom: 24px; }
</style>
