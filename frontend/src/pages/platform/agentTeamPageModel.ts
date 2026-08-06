export interface TeamNode {
  key: string
  label: string
  caption: string
  tone: 'accent' | 'blue' | 'orange' | 'purple' | 'green'
  detail: string
  input: string
  output: string
}

export interface TeamMember {
  key: string
  name: string
  role: string
  status: 'active' | 'inactive'
  detail: string
  agentKey: string
  graphType: 'report_generation' | 'report_chat'
}

export interface DomainRoute {
  label: string
  key: string
  desc: string
  targetAgent: string
  promptLabel: string
  priority: number
}

export interface TeamDetail {
  code: string
  graph: string
  members: TeamMember[]
  nodes: TeamNode[]
  routes: DomainRoute[]
}

const nodes: TeamNode[] = [
  { key: 'supervisor_route', label: 'Supervisor', caption: '识别领域 / 调度任务', tone: 'accent', detail: '根据请求内容判断业务领域，并把任务分发给对应的 Agent。', input: '用户问题、页面上下文', output: '业务领域、目标 Agent' },
  { key: 'query_operation_data', label: '运营数据 Agent', caption: '查询指标和业务数据', tone: 'blue', detail: '读取页面上下文、运营指标和业务数据，为后续分析提供事实基础。', input: '报告范围、业务域', output: '指标、业务记录、数据证据' },
  { key: 'detect_abnormal', label: '异常识别 Agent', caption: '识别异常和风险', tone: 'orange', detail: '依据阈值和规则识别异常指标、告警、隐患与未闭环事项。', input: '运营数据、阈值配置', output: '异常项、风险项、证据' },
  { key: 'domain_reason', label: '领域 Agent', caption: '原因分析 / 建议生成', tone: 'purple', detail: '结合业务领域分析异常原因、影响因素和处置优先级。', input: '异常项、风险项、领域 Prompt', output: '原因分析、建议草稿' },
  { key: 'summary', label: '报告汇总 Agent', caption: '输出完整分析报告', tone: 'green', detail: '汇总结论、证据链和建议动作，生成最终报告。', input: '分析结果、证据链', output: 'Markdown 报告、建议动作' },
]

const members: TeamMember[] = [
  { key: 'supervisor', name: 'Supervisor', role: '任务路由与流程调度', status: 'active', detail: '统一识别业务域、调度流程并记录执行上下文。', agentKey: 'supervisor', graphType: 'report_generation' },
  { key: 'query_operation_data', name: '运营数据 Agent', role: '查询页面上下文和业务指标', status: 'active', detail: '从运营数据源读取指标、告警、隐患和工单信息。', agentKey: 'operation', graphType: 'report_generation' },
  { key: 'detect_abnormal', name: '异常识别 Agent', role: '识别异常指标、告警和隐患', status: 'active', detail: '将业务数据转化为可解释的异常项和风险证据。', agentKey: 'operation', graphType: 'report_generation' },
  { key: 'domain_reason', name: '领域分析 Agent', role: '按业务领域分析异常原因', status: 'active', detail: '由 Supervisor 路由到安全、运维、经营或能力领域。', agentKey: 'operation', graphType: 'report_generation' },
  { key: 'domain_advice', name: '建议生成 Agent', role: '生成可执行的处理动作', status: 'active', detail: '输出带责任角色、优先级和依据的建议动作。', agentKey: 'operation', graphType: 'report_generation' },
  { key: 'summary', name: '报告汇总 Agent', role: '汇总报告正文和证据链', status: 'active', detail: '负责最终报告结构化输出和证据引用整理。', agentKey: 'operation', graphType: 'report_generation' },
]

const routes: DomainRoute[] = [
  { label: '本质安全', key: 'safety', desc: '告警、隐患、风险和整改建议', targetAgent: 'safety-agent', promptLabel: '本质安全分析策略', priority: 1 },
  { label: '设备运维', key: 'maintenance', desc: '设备缺陷、检维修和处置情况', targetAgent: 'maintenance-agent', promptLabel: '设备运维分析策略', priority: 2 },
  { label: '经营改善', key: 'business', desc: '经营指标、客户和履约改善', targetAgent: 'business-agent', promptLabel: '经营改善分析策略', priority: 3 },
  { label: '能力提升', key: 'capability', desc: '人员能力、效率和物联接入', targetAgent: 'capability-agent', promptLabel: '能力提升分析策略', priority: 4 },
]

export function buildTeamDetails(): TeamDetail {
  return {
    code: 'operation_analysis_team',
    graph: 'ioc_operation_analysis_graph',
    members: members.map((member) => ({ ...member })),
    nodes: nodes.map((node) => ({ ...node })),
    routes: routes.map((route) => ({ ...route })),
  }
}

export function getTeamMemberLinks(member: TeamMember) {
  return {
    agent: `/platform/agents?agent=${encodeURIComponent(member.agentKey)}`,
    graph: `/platform/graphs?type=${member.graphType}`,
  }
}

export function getRouteLinks(route: DomainRoute) {
  return {
    agent: `/platform/agents?agent=${encodeURIComponent(route.key)}`,
    prompt: `/prompt-center?domain=${encodeURIComponent(route.key)}`,
    graph: '/platform/graphs?type=report_generation',
  }
}
