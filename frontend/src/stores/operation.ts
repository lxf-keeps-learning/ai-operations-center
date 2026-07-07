import { defineStore } from 'pinia'
import { ref } from 'vue'

import { analyzeOperation, type OperationResult } from '@/api/operation'

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

  let stepTimer: ReturnType<typeof setInterval> | null = null

  function startStepProgress() {
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

  async function analyze(params: {
    trigger_type?: string
    domain?: string
    active_tab?: string
    time_dimension?: string
    date?: string
  }) {
    loading.value = true
    error.value = ''
    result.value = null
    currentStep.value = 0
    startStepProgress()

    try {
      result.value = await analyzeOperation(params)
      currentStep.value = STEPS.length - 1
    } catch (e) {
      error.value = e instanceof Error ? e.message : '分析请求失败'
    } finally {
      loading.value = false
      stopStepProgress()
    }
  }

  return {
    result,
    loading,
    error,
    currentStep,
    steps: STEPS,
    analyze,
  }
})
