<template>
  <div class="prompt-editor" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/prompt-center' }">Prompt 管理</el-breadcrumb-item>
        <el-breadcrumb-item :to="{ path: `/prompt-center/${promptId}` }">{{ prompt?.prompt_name || '编辑' }}</el-breadcrumb-item>
        <el-breadcrumb-item>编辑草稿</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="editor-layout">
      <div class="editor-left">
        <el-card>
          <template #header><span>基础信息</span></template>
          <el-form label-position="top">
            <el-form-item label="修改原因（必填）">
              <el-input v-model="form.change_reason" placeholder="请说明本次修改原因" />
            </el-form-item>
          </el-form>
        </el-card>

        <el-card class="section-card">
          <template #header><span>角色定义</span></template>
          <el-input v-model="form.business_role_content" type="textarea" :rows="4" placeholder="AI 应扮演的角色定义" />
        </el-card>

        <el-card class="section-card">
          <template #header><span>业务目标</span></template>
          <el-input v-model="form.business_goal_content" type="textarea" :rows="4" placeholder="本次分析的核心业务目标" />
        </el-card>

        <el-card class="section-card">
          <template #header>
            <div class="card-header">
              <span>规则列表</span>
              <el-button size="small" type="primary" @click="addRule">新增规则</el-button>
            </div>
          </template>
          <div v-for="(rule, i) in form.business_rules" :key="rule.key" class="rule-item">
            <div class="rule-header">
              <span class="rule-index">{{ i + 1 }}.</span>
              <el-switch v-model="rule.enabled" size="small" />
              <el-tag v-if="rule.required" size="small" type="danger">必填</el-tag>
              <el-button v-if="!rule.required" link type="danger" size="small" @click="form.business_rules.splice(i, 1)">删除</el-button>
              <el-button link type="info" size="small" @click="moveRule(i, -1)" :disabled="i === 0">上移</el-button>
              <el-button link type="info" size="small" @click="moveRule(i, 1)" :disabled="i === form.business_rules.length - 1">下移</el-button>
            </div>
            <el-input v-model="rule.content" type="textarea" :rows="2" placeholder="规则内容" />
          </div>
          <el-empty v-if="!form.business_rules.length" description="暂无规则" />
        </el-card>

        <el-card class="section-card">
          <template #header><span>输出要求</span></template>
          <el-input v-model="form.output_requirement" type="textarea" :rows="4" placeholder="输出格式、长度、语言等要求" />
        </el-card>

        <el-card class="section-card">
          <template #header><span>正例</span></template>
          <div v-for="(ex, i) in form.positive_examples" :key="i" class="example-item">
            <el-input v-model="ex.title" placeholder="标题" style="margin-bottom: 8px" />
            <el-input v-model="ex.content" type="textarea" :rows="2" placeholder="内容" />
            <el-button link type="danger" size="small" @click="form.positive_examples.splice(i, 1)">删除</el-button>
          </div>
          <el-button size="small" @click="form.positive_examples.push({ title: '', content: '' })">新增正例</el-button>
        </el-card>

        <el-card class="section-card">
          <template #header><span>反例</span></template>
          <div v-for="(ex, i) in form.negative_examples" :key="i" class="example-item">
            <el-input v-model="ex.title" placeholder="标题" style="margin-bottom: 8px" />
            <el-input v-model="ex.content" type="textarea" :rows="2" placeholder="内容" />
            <el-button link type="danger" size="small" @click="form.negative_examples.splice(i, 1)">删除</el-button>
          </div>
          <el-button size="small" @click="form.negative_examples.push({ title: '', content: '' })">新增反例</el-button>
        </el-card>

        <div class="form-actions">
          <el-button @click="saveDraft" :loading="saving">保存草稿</el-button>
          <el-button type="primary" @click="createNewVersion" :loading="creating">创建版本</el-button>
        </div>
      </div>

      <div class="editor-right">
        <el-card>
          <template #header><span>最终 Prompt 预览</span></template>
          <div v-if="previewMessages.length">
            <div v-for="(msg, i) in previewMessages" :key="i" class="preview-msg">
              <div class="preview-role">{{ msg.role }}</div>
              <pre class="preview-content">{{ msg.content }}</pre>
            </div>
          </div>
          <el-empty v-else description="保存后生成预览" />
        </el-card>

        <el-card class="section-card">
          <template #header><span>动态变量</span></template>
          <el-table :data="prompt?.variables || []" size="small" max-height="300">
            <el-table-column prop="variable_key" label="Key" width="120" />
            <el-table-column prop="variable_name" label="名称" width="100" />
            <el-table-column prop="description" label="说明" />
          </el-table>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as api from '@/api/prompt-center'
import type { PromptDetail, RuleItem, ExampleItem, PromptStatus, VersionCreate } from '@/types/prompt-center'

const route = useRoute()
const promptId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const creating = ref(false)
const prompt = ref<PromptDetail | null>(null)
const currentVersionId = ref<number | null>(null)
const currentVersionStatus = ref<PromptStatus | null>(null)

const form = reactive({
  change_reason: '',
  business_role_content: '',
  business_goal_content: '',
  business_rules: [] as RuleItem[],
  output_requirement: '',
  positive_examples: [] as ExampleItem[],
  negative_examples: [] as ExampleItem[],
})

const previewMessages = ref<any[]>([])

onMounted(async () => {
  loading.value = true
  try {
    prompt.value = await api.getPrompt(promptId.value)
    const versionId = prompt.value.current_version_id || prompt.value.versions[0]?.id
    if (versionId) {
      try {
        const version = await api.getVersion(promptId.value, versionId)
        currentVersionId.value = version.id
        currentVersionStatus.value = version.status
        form.business_role_content = version.business_role_content || ''
        form.business_goal_content = version.business_goal_content || ''
        form.business_rules = version.business_rules || []
        form.output_requirement = version.output_requirement || ''
        form.positive_examples = version.positive_examples || []
        form.negative_examples = version.negative_examples || []
      } catch { }
    }
  } finally {
    loading.value = false
  }
})

function addRule() {
  form.business_rules.push({
    key: `rule_${Date.now()}`,
    content: '',
    enabled: true,
    required: false,
    display_order: form.business_rules.length,
  })
}

function moveRule(index: number, direction: number) {
  const target = index + direction
  if (target < 0 || target >= form.business_rules.length) return;
  [form.business_rules[index], form.business_rules[target]] = [form.business_rules[target], form.business_rules[index]]
}

async function saveDraft() {
  if (!form.change_reason) {
    ElMessage.warning('请填写修改原因')
    return
  }
  saving.value = true
  try {
    const payload = buildVersionPayload()
    const version = currentVersionId.value
      && (currentVersionStatus.value === 'draft' || currentVersionStatus.value === 'rejected')
      ? await api.updateVersion(promptId.value, currentVersionId.value, payload)
      : await api.createVersion(promptId.value, payload)
    currentVersionId.value = version.id
    currentVersionStatus.value = version.status
    const preview = await api.previewPrompt(promptId.value, version.id, {})
    previewMessages.value = preview.messages || []
    ElMessage.success(`草稿 v${version.version} 已保存`)
  } catch (e: any) {
    ElMessage.error(e.message || '保存草稿失败')
  } finally {
    saving.value = false
  }
}

async function createNewVersion() {
  if (!form.change_reason) {
    ElMessage.warning('请填写修改原因')
    return
  }
  creating.value = true
  try {
    const version = await api.createVersion(promptId.value, buildVersionPayload())
    currentVersionId.value = version.id
    currentVersionStatus.value = version.status
    ElMessage.success(`版本 v${version.version} 创建成功`)

    const result = await api.previewPrompt(promptId.value, version.id, {})
    previewMessages.value = result.messages || []
  } catch (e: any) {
    ElMessage.error(e.message || '创建版本失败')
  } finally {
    creating.value = false
  }
}

function buildVersionPayload(): VersionCreate {
  return {
    business_role_content: form.business_role_content || undefined,
    business_goal_content: form.business_goal_content || undefined,
    business_rules: form.business_rules.length ? form.business_rules : undefined,
    output_requirement: form.output_requirement || undefined,
    positive_examples: form.positive_examples.length ? form.positive_examples : undefined,
    negative_examples: form.negative_examples.length ? form.negative_examples : undefined,
    change_reason: form.change_reason,
  }
}
</script>

<style scoped>
.prompt-editor { padding: 24px; }
.page-header { margin-bottom: 24px; }
.editor-layout { display: flex; gap: 24px; align-items: flex-start; }
.editor-left { flex: 1; max-width: 65%; }
.editor-right { flex: 0 0 35%; position: sticky; top: 24px; }
.section-card { margin-top: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.rule-item { margin-bottom: 12px; padding: 12px; background: #fafafa; border-radius: 4px; border: 1px solid #ebeef5; }
.rule-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.rule-index { font-weight: 600; color: #909399; }
.example-item { margin-bottom: 12px; padding: 12px; background: #fafafa; border-radius: 4px; }
.form-actions { margin-top: 24px; display: flex; gap: 12px; justify-content: flex-end; }
.preview-msg { margin-bottom: 12px; }
.preview-role { background: #f5f7fa; padding: 6px 12px; font-weight: 600; font-size: 12px; border: 1px solid #ebeef5; border-bottom: none; border-radius: 4px 4px 0 0; }
.preview-content { margin: 0; padding: 12px; border: 1px solid #ebeef5; border-radius: 0 0 4px 4px; white-space: pre-wrap; font-size: 12px; line-height: 1.5; background: #fff; max-height: 300px; overflow-y: auto; }
</style>
