export type AgentGraphType = 'report_generation' | 'report_chat'

export interface AgentDetail {
  key: string
  name: string
  description: string
  status: 'active' | 'inactive'
  graphs: number
  model: string
  promptLabel: string
  graphType: AgentGraphType
  responsibilities: string[]
  recentRun: string
  successRate: string
  averageDuration: string
  tokenUsage: string
}

export interface AgentActionLinks {
  graph: string
  prompt: string
  model: string
}

const agentDefinitions: AgentDetail[] = [
  {
    key: 'operation',
    name: '运营分析 Agent',
    description: '负责生成运营分析报告，汇总异常、风险和建议动作。',
    status: 'active',
    graphs: 1,
    model: '默认运行时',
    promptLabel: '运营分析默认策略',
    graphType: 'report_generation',
    responsibilities: ['读取运营指标与页面上下文', '识别异常、风险和影响范围', '生成可执行的建议动作'],
    recentRun: '最近 8 分钟前',
    successRate: '98.4%',
    averageDuration: '12.8 s',
    tokenUsage: '12.4k / 次',
  },
  {
    key: 'report_chat',
    name: '报告追问 Agent',
    description: '围绕已生成报告进行证据检索、RAG 补充和追问回答。',
    status: 'active',
    graphs: 1,
    model: '默认运行时',
    promptLabel: '报告追问默认策略',
    graphType: 'report_chat',
    responsibilities: ['加载报告上下文与对话记忆', '检索报告证据和知识库内容', '生成带依据的追问回答'],
    recentRun: '最近 2 分钟前',
    successRate: '96.7%',
    averageDuration: '8.6 s',
    tokenUsage: '4.8k / 次',
  },
]

export function buildAgentDetails(): AgentDetail[] {
  return agentDefinitions.map((agent) => ({
    ...agent,
    responsibilities: [...agent.responsibilities],
  }))
}

export function getAgentActionLinks(agent: AgentDetail): AgentActionLinks {
  return {
    graph: `/platform/graphs?type=${agent.graphType}`,
    prompt: `/prompt-center?agent=${encodeURIComponent(agent.key)}`,
    model: `/infra/models?agent=${encodeURIComponent(agent.key)}`,
  }
}
