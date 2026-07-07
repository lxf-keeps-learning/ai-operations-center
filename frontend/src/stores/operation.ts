import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  analyzeOperation,
  type OperationAnalyzeParams,
  type OperationResult,
} from '@/api/operation'

const STEPS = [
  '初始化分析环境',
  '查询 KPI 运营数据',
  '检测异常指标',
  'AI 分析异常原因',
  'AI 生成改进建议',
  '汇总分析结论',
]

export const useOperationStore = defineStore('operation', () => {
  const result = ref<OperationResult | null>(null)
  const loading = ref(false)
  const error = ref('')
  const currentStep = ref(0)
  const currentParams = ref<OperationAnalyzeParams | null>(null)
  const currentKey = ref('')

  let stepTimer: ReturnType<typeof setInterval> | null = null
  let requestSeq = 0

  function startStepProgress() {
    stopStepProgress()
    currentStep.value = 0
    stepTimer = setInterval(() => {
      if (currentStep.value < STEPS.length - 1) {
        currentStep.value++
      }
    }, 4000)
  }

  function stopStepProgress() {
    if (stepTimer) {
      clearInterval(stepTimer)
      stepTimer = null
    }
  }

  function reset() {
    requestSeq++
    stopStepProgress()
    result.value = null
    loading.value = false
    error.value = ''
    currentStep.value = 0
    currentParams.value = null
    currentKey.value = ''
  }

  async function analyze(params: OperationAnalyzeParams, key = buildRequestKey(params)) {
    const seq = ++requestSeq

    loading.value = true
    error.value = ''
    result.value = null
    currentStep.value = 0
    currentParams.value = { ...params }
    currentKey.value = key
    startStepProgress()

    try {
      const data = await analyzeOperation(params)
      if (seq !== requestSeq) {
        return
      }
      result.value = data
      currentStep.value = STEPS.length - 1
    } catch (e) {
      if (seq !== requestSeq) {
        return
      }
      error.value = e instanceof Error ? e.message : '分析请求失败'
    } finally {
      if (seq === requestSeq) {
        loading.value = false
        stopStepProgress()
      }
    }
  }

  return {
    result,
    loading,
    error,
    currentStep,
    currentParams,
    currentKey,
    steps: STEPS,
    analyze,
    reset,
  }
})

export function buildRequestKey(params: OperationAnalyzeParams): string {
  return [
    params.domain || 'safety',
    params.active_tab || '',
    params.time_dimension || 'month',
    params.date || '',
    params.company_id || '',
    params.project_id || '',
    params.user_question || '',
  ].join('|')
}
