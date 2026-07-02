import type { AgentAnalyzeRequest, PageContext } from '@/types/api'

export function createOperationPageContext(): PageContext {
  return {
    page: 'operation_center',
    filters: {
      date: new Date().toISOString().slice(0, 10),
      org_id: 'demo_org',
      scope: 'group',
    },
  }
}

export function createOperationAnalyzePayload(): AgentAnalyzeRequest {
  return {
    agent_code: 'operation',
    scene_code: 'operation_daily_summary',
    message: '生成今日运营摘要，并识别需要优先关注的风险。',
    conversation_id: null,
    page_context: createOperationPageContext(),
    business_context: {
      object_type: 'operation_dashboard',
      object_id: 'dashboard_demo',
    },
    stream: true,
  }
}
