import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import type { OperationAnalyzeParams } from '@/api/operation'
import { streamOperationAnalysis } from '@/services/analysisStream'
import type { AnalysisEventStatus, AnalysisStreamEvent } from '@/types/analysisStream'

export interface AnalysisStep {
  key: string
  title: string
  status: AnalysisEventStatus
  message: string
  startedAt: string | null
  completedAt: string | null
  durationMs: number | null
  sourceLabel: string
  errorMessage: string
}

export type AnalysisRunStatus = 'idle' | 'running' | 'completed' | 'failed'

const INITIAL_STEPS: AnalysisStep[] = [
  { key: 'init_context', title: '初始化环境', status: 'pending', message: '', startedAt: null, completedAt: null, durationMs: null, sourceLabel: '', errorMessage: '' },
  { key: 'query_operation_data', title: '运营数据查询', status: 'pending', message: '', startedAt: null, completedAt: null, durationMs: null, sourceLabel: '', errorMessage: '' },
  { key: 'detect_abnormal', title: '异常识别', status: 'pending', message: '', startedAt: null, completedAt: null, durationMs: null, sourceLabel: '', errorMessage: '' },
  { key: 'analyze_reason', title: '原因分析', status: 'pending', message: '', startedAt: null, completedAt: null, durationMs: null, sourceLabel: '', errorMessage: '' },
  { key: 'generate_advice', title: '建议动作生成', status: 'pending', message: '', startedAt: null, completedAt: null, durationMs: null, sourceLabel: '', errorMessage: '' },
  { key: 'summary', title: '报告汇总', status: 'pending', message: '', startedAt: null, completedAt: null, durationMs: null, sourceLabel: '', errorMessage: '' },
]

export const useAnalysisProgressStore = defineStore('analysisProgress', () => {
  const runId = ref('')
  const status = ref<AnalysisRunStatus>('idle')
  const steps = ref<AnalysisStep[]>(JSON.parse(JSON.stringify(INITIAL_STEPS)))
  const currentNodeKey = ref('')
  const report = ref<Record<string, unknown> | null>(null)
  const streamedReport = ref('')
  const error = ref('')
  const loading = ref(false)
  const lastSequence = ref(0)

  let streamController: { abort: () => void } | null = null

  const currentStepIndex = computed(() => {
    const idx = steps.value.findIndex(s => s.status === 'running')
    return idx >= 0 ? idx : steps.value.filter(s => s.status === 'completed').length
  })

  function handleStreamEvent(event: AnalysisStreamEvent) {
    // SSE 重连或服务端事件回放可能带来重复/乱序数据。sequence 是同一
    // run 内的单调序号，旧事件不能覆盖已经展示的新状态。
    if (event.run_id === runId.value && event.sequence <= lastSequence.value) return
    if (runId.value && event.run_id !== runId.value && event.event_type !== 'analysis_started') return
    lastSequence.value = event.sequence

    switch (event.event_type) {
      case 'analysis_started':
        status.value = 'running'
        runId.value = event.run_id
        loading.value = true
        break

      case 'node_started':
        currentNodeKey.value = event.node_key || ''
        updateStep(event.node_key || '', {
          status: 'running',
          message: event.message,
          startedAt: event.timestamp,
        })
        break

      case 'node_completed':
        updateStep(event.node_key || '', {
          status: 'completed',
          message: event.message,
          completedAt: event.timestamp,
          durationMs: event.duration_ms ?? null,
          sourceLabel: event.source_label || '',
        })
        break

      case 'node_failed':
        updateStep(event.node_key || '', {
          status: 'failed',
          message: event.message,
          errorMessage: event.error_message || '节点执行失败',
        })
        status.value = 'failed'
        error.value = event.error_message || `${event.node_name || event.node_key} 执行失败`
        break

      case 'report_completed':
        status.value = 'completed'
        report.value = event.payload || null
        if (typeof event.payload?.summary === 'string') {
          streamedReport.value = event.payload.summary
        }
        loading.value = false
        break

      case 'report_delta': {
        const delta = event.payload?.delta
        if (typeof delta === 'string') streamedReport.value += delta
        break
      }

      case 'analysis_failed':
        status.value = 'failed'
        error.value = event.error_message || '分析任务执行失败'
        loading.value = false
        break

      case 'cancelled':
        status.value = 'failed'
        error.value = event.message || '请求已被取消'
        loading.value = false
        break

      case 'stream_closed':
        if (status.value === 'running' && !report.value && !error.value) {
          status.value = 'failed'
          error.value = '事件流已关闭，但未收到报告完成事件'
        }
        loading.value = false
        break

      case 'heartbeat':
        break
    }
  }

  function updateStep(key: string, updates: Partial<AnalysisStep>) {
    const step = steps.value.find(s => s.key === key)
    if (step) {
      Object.assign(step, updates)
    }
  }

  function startStreamAnalysis(params: OperationAnalyzeParams) {
    resetProgress()

    status.value = 'running'
    loading.value = true

    streamController = streamOperationAnalysis(params, {
      onEvent: handleStreamEvent,
      onError(err) {
        status.value = 'failed'
        error.value = err.message
        loading.value = false
      },
      onClose() {
        streamController = null
        if (loading.value && status.value === 'running') {
          status.value = 'failed'
          error.value = error.value || '事件流已中断，请稍后重试'
          loading.value = false
        }
      },
    })
  }

  function cancelStream() {
    if (streamController) {
      streamController.abort()
      streamController = null
    }
    if (loading.value) {
      loading.value = false
    }
  }

  function resetProgress() {
    cancelStream()
    runId.value = ''
    status.value = 'idle'
    steps.value = JSON.parse(JSON.stringify(INITIAL_STEPS))
    currentNodeKey.value = ''
    report.value = null
    streamedReport.value = ''
    error.value = ''
    loading.value = false
    lastSequence.value = 0
  }

  return {
    runId,
    status,
    steps,
    currentNodeKey,
    report,
    streamedReport,
    error,
    loading,
    lastSequence,
    currentStepIndex,
    handleStreamEvent,
    startStreamAnalysis,
    cancelStream,
    resetProgress,
  }
})
