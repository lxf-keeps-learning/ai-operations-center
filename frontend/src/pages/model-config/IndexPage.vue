<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { getModels, selectModel } from '@/api/config'
import type { ModelProvider } from '@/types/config'

const supportedProviders = ['deepseek', 'doubao', 'zhipu']
const providerLabels: Record<string, string> = { deepseek: 'DS / DeepSeek', doubao: '豆包', zhipu: '智谱' }
const models = ref<ModelProvider[]>([])
const selectedProvider = ref('deepseek')
const selectedModel = ref('')
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')

const providers = computed(() => models.value.filter((item) => supportedProviders.includes(item.provider)))
const currentProvider = computed(() => providers.value.find((item) => item.provider === selectedProvider.value) || providers.value[0])
const modelVersions = computed(() => currentProvider.value?.modelVersions || (currentProvider.value?.model ? [currentProvider.value.model] : []))

watch(selectedProvider, () => {
  const provider = currentProvider.value
  selectedModel.value = provider?.model || provider?.modelVersions?.[0] || ''
  notice.value = ''
})

function providerName(provider: string) { return providerLabels[provider] || provider }
function isSelected(item: ModelProvider) { return item.provider === selectedProvider.value }

async function loadModels() {
  loading.value = true; error.value = ''
  try {
    models.value = await getModels()
    const defaultProvider = models.value.find((item) => item.default && supportedProviders.includes(item.provider))
    selectedProvider.value = defaultProvider?.provider || 'deepseek'
    selectedModel.value = defaultProvider?.model || defaultProvider?.modelVersions?.[0] || ''
  } catch {
    // 配置接口暂不可用时使用空状态，不把 502 等网关错误暴露给用户。
    models.value = []
    error.value = ''
  }
  finally { loading.value = false }
}

async function saveSelection() {
  if (!selectedProvider.value || !selectedModel.value || saving.value) return
  saving.value = true; error.value = ''; notice.value = ''
  try {
    const updated = await selectModel(selectedProvider.value, selectedModel.value)
    models.value = models.value.map((item) => ({ ...item, default: item.provider === updated.provider, model: item.provider === updated.provider ? updated.model : item.model }))
    notice.value = `已切换为 ${providerName(updated.provider)} / ${updated.model}`
  } catch (err) { error.value = err instanceof Error ? err.message : '模型切换失败' }
  finally { saving.value = false }
}

onMounted(loadModels)
</script>

<template>
  <div class="model-config">
    <div class="model-config__header"><div><h1>模型配置</h1><p>选择默认模型供应商和模型版本，API Key 仅存储在后端。</p></div><button class="refresh-btn" type="button" @click="loadModels">刷新</button></div>
    <div v-if="loading" class="page-loading">加载中...</div>
    <p v-else-if="error" class="page-error">{{ error }}</p>
    <div v-else-if="!providers.length" class="empty-state">
      <strong>暂无数据</strong>
      <span>当前没有可用的模型配置，请稍后刷新。</span>
      <button type="button" @click="loadModels">重新加载</button>
    </div>
    <template v-else>
      <section class="selection-card"><div class="selection-card__title"><div><h2>当前默认模型</h2><p>新的 Runtime Chat、报告生成和报告追问将使用此选择。</p></div><span class="selection-badge">{{ currentProvider?.default ? '当前默认' : '待保存' }}</span></div><div class="provider-tabs"><button v-for="provider in providers" :key="provider.provider" type="button" :class="{ active: isSelected(provider) }" @click="selectedProvider = provider.provider"><strong>{{ providerName(provider.provider) }}</strong><small>{{ provider.enabled ? '已启用' : '未启用' }}</small></button></div><div class="model-picker"><label for="model-version">模型版本</label><select id="model-version" v-model="selectedModel"><option v-for="version in modelVersions" :key="version" :value="version">{{ version }}</option></select><button type="button" :disabled="saving || !selectedModel" @click="saveSelection">{{ saving ? '保存中...' : '保存选择' }}</button></div><p v-if="notice" class="page-success">{{ notice }}</p></section>
      <section class="provider-grid"><article v-for="provider in providers" :key="provider.provider" class="provider-card" :class="{ 'provider-card--active': provider.default }"><div class="provider-card__header"><div><h2>{{ providerName(provider.provider) }}</h2><span>{{ provider.provider }}</span></div><em v-if="provider.default">默认</em></div><div class="provider-card__model"><span>当前版本</span><code>{{ provider.model }}</code></div><div class="provider-card__versions"><span>可选版本</span><div><b v-for="version in provider.modelVersions" :key="version" :class="{ selected: version === provider.model }">{{ version }}</b></div></div><div class="provider-card__limits"><span>输入 {{ provider.maxInputTokens.toLocaleString() }} Token</span><span>输出 {{ provider.maxOutputTokens.toLocaleString() }} Token</span><span>{{ provider.rpmLimit }} RPM</span></div></article></section>
    </template>
  </div>
</template>

<style scoped>
.model-config { max-width: 1250px; }.model-config__header { align-items: center; display: flex; justify-content: space-between; }.model-config h1 { color: #14213d; font-size: 26px; margin: 0 0 5px; }.model-config__header p, .selection-card__title p { color: #71809b; font-size: 13px; margin: 0; }.refresh-btn { background: #172554; border: 0; border-radius: 8px; color: #fff; cursor: pointer; font-weight: 700; padding: 10px 16px; }.selection-card { background: #fff; border: 1px solid #dfe6f1; border-radius: 12px; margin-top: 24px; padding: 22px; }.selection-card__title { align-items: flex-start; display: flex; justify-content: space-between; }.selection-card h2 { color: #1e293b; font-size: 18px; margin: 0 0 5px; }.selection-badge { background: #dcfce7; border-radius: 999px; color: #166534; font-size: 11px; padding: 5px 9px; }.provider-tabs { display: grid; gap: 10px; grid-template-columns: repeat(3, 1fr); margin-top: 22px; }.provider-tabs button { background: #f8fafc; border: 1px solid #dfe6f1; border-radius: 9px; cursor: pointer; padding: 14px; text-align: left; }.provider-tabs button.active { background: #eef2ff; border-color: #6366f1; box-shadow: inset 3px 0 #6366f1; }.provider-tabs strong, .provider-tabs small { display: block; }.provider-tabs strong { color: #334155; font-size: 14px; }.provider-tabs small { color: #94a3b8; font-size: 11px; margin-top: 5px; }.model-picker { align-items: end; display: flex; gap: 10px; margin-top: 18px; }.model-picker label { color: #64748b; font-size: 12px; }.model-picker select { background: #fff; border: 1px solid #cbd5e1; border-radius: 7px; color: #334155; flex: 1; font: inherit; padding: 10px 12px; }.model-picker button { background: #4338ca; border: 0; border-radius: 7px; color: #fff; cursor: pointer; font-weight: 700; padding: 11px 18px; }.model-picker button:disabled { cursor: not-allowed; opacity: .55; }.page-success { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 7px; color: #166534; font-size: 12px; margin: 14px 0 0; padding: 9px 12px; }.provider-grid { display: grid; gap: 14px; grid-template-columns: repeat(3, 1fr); margin-top: 16px; }.provider-card { background: #fff; border: 1px solid #dfe6f1; border-radius: 11px; padding: 18px; }.provider-card--active { border-color: #6366f1; box-shadow: 0 6px 20px rgba(79,70,229,.08); }.provider-card__header { align-items: flex-start; display: flex; justify-content: space-between; }.provider-card h2 { color: #1e293b; font-size: 16px; margin: 0 0 4px; }.provider-card__header span { color: #94a3b8; font-family: ui-monospace, monospace; font-size: 11px; }.provider-card em { background: #dcfce7; border-radius: 999px; color: #166534; font-size: 10px; font-style: normal; padding: 4px 7px; }.provider-card__model, .provider-card__versions { border-top: 1px solid #edf1f7; margin-top: 15px; padding-top: 13px; }.provider-card__model span, .provider-card__versions > span { color: #94a3b8; display: block; font-size: 11px; margin-bottom: 7px; }.provider-card__model code { color: #4f46e5; font-size: 13px; }.provider-card__versions div { display: flex; flex-wrap: wrap; gap: 5px; }.provider-card__versions b { background: #f1f5f9; border-radius: 4px; color: #64748b; font-size: 10px; font-weight: 500; padding: 4px 6px; }.provider-card__versions b.selected { background: #eef2ff; color: #4338ca; }.provider-card__limits { color: #94a3b8; display: flex; flex-wrap: wrap; font-size: 10px; gap: 8px; margin-top: 18px; }.page-loading { color: #71809b; padding: 50px 0; }.page-error { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #b91c1c; padding: 12px 16px; }.empty-state { align-items: center; background: #fff; border: 1px dashed #cbd5e1; border-radius: 12px; color: #71809b; display: flex; flex-direction: column; gap: 8px; margin-top: 24px; padding: 64px 20px; text-align: center; }.empty-state strong { color: #475569; font-size: 16px; }.empty-state span { font-size: 13px; }.empty-state button { background: #4338ca; border: 0; border-radius: 7px; color: #fff; cursor: pointer; font-size: 12px; margin-top: 8px; padding: 8px 14px; }
@media (max-width: 900px) { .provider-grid { grid-template-columns: 1fr; }.provider-tabs { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .model-picker { align-items: stretch; flex-direction: column; }.model-config__header { align-items: flex-start; gap: 15px; } }
</style>
