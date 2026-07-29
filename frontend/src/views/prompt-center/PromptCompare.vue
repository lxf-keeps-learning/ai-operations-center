<template>
  <div class="prompt-compare" v-loading="loading">
    <div class="page-header">
      <el-breadcrumb>
        <el-breadcrumb-item :to="{ path: '/prompt-center' }">Prompt 管理</el-breadcrumb-item>
        <el-breadcrumb-item>版本对比</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <el-form :inline="true">
      <el-form-item label="源版本">
        <el-select v-model="sourceVersionId" placeholder="选择源版本">
          <el-option v-for="v in versions" :key="v.id" :label="`v${v.version}`" :value="v.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="目标版本">
        <el-select v-model="targetVersionId" placeholder="选择目标版本">
          <el-option v-for="v in versions" :key="v.id" :label="`v${v.version}`" :value="v.id" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="loadCompare">对比</el-button>
      </el-form-item>
    </el-form>

    <template v-if="compareResult">
      <el-alert
        :title="`发现 ${compareResult.diffs.length} 处差异`"
        :type="compareResult.diffs.length ? 'warning' : 'success'"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      />

      <div v-for="diff in compareResult.diffs" :key="diff.field" class="diff-card">
        <div class="diff-header">
          <el-tag :type="diff.changeTypeTag" size="small">{{ diff.changeTypeLabel }}</el-tag>
          <span class="diff-field">{{ diff.field_label }}</span>
        </div>
        <div class="diff-content">
          <div class="diff-side diff-source">
            <div class="diff-side-header">源版本 v{{ compareResult.source_version.version }}</div>
            <pre class="diff-text">{{ diff.source_value || '（空）' }}</pre>
          </div>
          <div class="diff-side diff-target">
            <div class="diff-side-header">目标版本 v{{ compareResult.target_version.version }}</div>
            <pre class="diff-text">{{ diff.target_value || '（空）' }}</pre>
          </div>
        </div>
      </div>

      <el-empty v-if="!compareResult.diffs.length" description="两个版本内容完全相同" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import * as api from '@/api/prompt-center'
import type { DiffItem, PromptVersionSummary, VersionCompare } from '@/types/prompt-center'

type DisplayDiffItem = DiffItem & {
  changeTypeTag: 'success' | 'warning' | 'danger'
  changeTypeLabel: string
}

type DisplayVersionCompare = Omit<VersionCompare, 'diffs'> & {
  diffs: DisplayDiffItem[]
}

const route = useRoute()
const promptId = computed(() => Number(route.params.id))
const loading = ref(false)
const versions = ref<PromptVersionSummary[]>([])
const sourceVersionId = ref<number | null>(null)
const targetVersionId = ref<number | null>(null)
const compareResult = ref<DisplayVersionCompare | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    const data = await api.listVersions(promptId.value)
    versions.value = data
    if (versions.value.length >= 2) {
      sourceVersionId.value = versions.value[0].id
      targetVersionId.value = versions.value[1].id
      loadCompare()
    }
  } finally {
    loading.value = false
  }
})

async function loadCompare() {
  if (!sourceVersionId.value || !targetVersionId.value) return
  loading.value = true
  try {
    const result = await api.compareVersions(promptId.value, sourceVersionId.value, targetVersionId.value)
    compareResult.value = {
      ...result,
      diffs: result.diffs.map(d => ({
      ...d,
      changeTypeTag: d.change_type === 'modified' ? 'warning' : d.change_type === 'added' ? 'success' : 'danger',
      changeTypeLabel: d.change_type === 'modified' ? '修改' : d.change_type === 'added' ? '新增' : '删除',
      })),
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.prompt-compare { padding: 24px; }
.page-header { margin-bottom: 24px; }
.diff-card { margin-bottom: 16px; border: 1px solid #ebeef5; border-radius: 8px; overflow: hidden; }
.diff-header { padding: 12px 16px; background: #f5f7fa; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #ebeef5; }
.diff-field { font-weight: 600; }
.diff-content { display: flex; }
.diff-side { flex: 1; min-width: 0; }
.diff-source { border-right: 1px solid #ebeef5; }
.diff-side-header { padding: 8px 12px; background: #fafafa; font-size: 12px; color: #909399; border-bottom: 1px solid #ebeef5; }
.diff-text { margin: 0; padding: 12px; white-space: pre-wrap; font-size: 12px; line-height: 1.5; }
.diff-target .diff-text { background: #f0f9eb; }
.diff-source .diff-text { background: #fef0f0; }
</style>
