import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  PromptDefinition,
  PromptDetail,
  PromptVersion,
  PromptVersionSummary,
  TestRun,
  Release,
  PromptMetrics,
} from '@/types/prompt-center'
import * as api from '@/api/prompt-center'

export const usePromptCenterStore = defineStore('promptCenter', () => {
  const promptList = ref<PromptDefinition[]>([])
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)

  const currentPrompt = ref<PromptDetail | null>(null)
  const versions = ref<PromptVersionSummary[]>([])
  const currentVersion = ref<PromptVersion | null>(null)
  const testRuns = ref<TestRun[]>([])
  const releases = ref<Release[]>([])
  const metrics = ref<PromptMetrics | null>(null)

  const searchQuery = ref('')
  const statusFilter = ref('')
  const sceneFilter = ref('')
  const graphFilter = ref('')

  async function fetchPrompts(page = 1) {
    loading.value = true
    try {
      const params: Record<string, string | number> = { page, page_size: pageSize.value }
      if (searchQuery.value) params.search = searchQuery.value
      if (statusFilter.value) params.status = statusFilter.value
      if (sceneFilter.value) params.business_scene = sceneFilter.value
      if (graphFilter.value) params.graph_name = graphFilter.value

      const result = await api.listPrompts(params)
      promptList.value = result.items
      total.value = result.total
      currentPage.value = page
    } finally {
      loading.value = false
    }
  }

  async function fetchPromptDetail(promptId: number) {
    currentPrompt.value = await api.getPrompt(promptId)
    versions.value = await api.listVersions(promptId)
    return currentPrompt.value
  }

  async function fetchVersions(promptId: number) {
    versions.value = await api.listVersions(promptId)
    return versions.value
  }

  async function fetchMetrics(promptId: number) {
    metrics.value = await api.getPromptMetrics(promptId)
    return metrics.value
  }

  async function fetchReleases(promptId: number) {
    releases.value = await api.listReleases(promptId)
    return releases.value
  }

  return {
    promptList, total, currentPage, pageSize, loading,
    currentPrompt, versions, currentVersion, testRuns, releases, metrics,
    searchQuery, statusFilter, sceneFilter, graphFilter,
    fetchPrompts, fetchPromptDetail, fetchVersions, fetchMetrics, fetchReleases,
  }
})
