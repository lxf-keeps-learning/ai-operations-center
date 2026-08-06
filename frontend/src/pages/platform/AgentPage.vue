<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  buildAgentDetails,
  getAgentActionLinks,
  type AgentDetail,
} from './agentPageModel'

type DrawerMode = 'detail' | 'config'

const agents = buildAgentDetails()
const selectedAgent = ref<AgentDetail | null>(null)
const drawerMode = ref<DrawerMode>('detail')
const drawerTitle = computed(() => drawerMode.value === 'detail' ? 'Agent 详情' : 'Agent 配置入口')
const selectedLinks = computed(() => selectedAgent.value ? getAgentActionLinks(selectedAgent.value) : null)

const reportGraph = [
  { key: 'supervisor_route', label: 'Supervisor 路由', description: '识别业务领域并选择对应领域 Agent' },
  { key: 'init_context', label: '初始化环境', description: '建立请求上下文和执行状态' },
  { key: 'query_operation_data', label: '运营数据查询', description: '查询页面上下文和业务指标' },
  { key: 'detect_abnormal', label: '异常识别', description: '识别异常指标、告警和隐患' },
  { key: 'domain_reason', label: '领域原因分析', description: '分析异常原因和影响因素' },
  { key: 'domain_advice', label: '领域建议生成', description: '生成针对性的处理建议' },
  { key: 'summary', label: '报告汇总', description: '汇总报告正文和证据链' },
]

const chatGraph = [
  { key: 'load_report_context', label: '加载报告上下文', description: '读取目标报告和分析依据' },
  { key: 'load_chat_memory', label: '加载对话记忆', description: '读取当前追问会话历史' },
  { key: 'classify_question_scope', label: '问题范围分类', description: '判断问题属于报告内、关联知识或越界问题' },
  { key: 'retrieve_report_evidence', label: '报告证据检索', description: '在报告内容中检索相关证据' },
  { key: 'should_use_rag', label: 'RAG 判断', description: '判断是否需要补充知识库' },
  { key: 'rag_branch', label: '知识库检索分支', description: '构建查询、检索知识库并融合上下文' },
  { key: 'generate_report_answer', label: '生成回答', description: '基于报告和证据生成回答' },
  { key: 'persist_chat_message', label: '持久化消息', description: '保存问题、回答和引用关系' },
]

function openDetails(agent: AgentDetail) {
  selectedAgent.value = agent
  drawerMode.value = 'detail'
}

function openConfig(agent: AgentDetail) {
  selectedAgent.value = agent
  drawerMode.value = 'config'
}

function closeDrawer() {
  selectedAgent.value = null
}
</script>

<template>
  <div class="agent-page">
    <header class="agent-page__header">
      <div>
        <div class="agent-eyebrow">AGENT RUNTIME / CONTROL CENTER</div>
        <h1>Agent</h1>
        <p>查看智能体职责、运行指标，并进入 Prompt、模型和 Graph 的真实配置页面。</p>
      </div>
      <div class="agent-page__summary">
        <span class="agent-count">{{ agents.length }} 个 Agent · {{ agents.length }} 条 Graph</span>
        <RouterLink class="agent-run-link" to="/platform/graphs">查看全部运行 →</RouterLink>
      </div>
    </header>

    <section class="agent-overview">
      <article v-for="agent in agents" :key="agent.key" class="agent-card">
        <div class="agent-card__icon">♙</div>
        <div class="agent-card__body">
          <div class="agent-card__title">
            <h2>{{ agent.name }}</h2>
            <span class="agent-status"><i />{{ agent.status === 'active' ? '运行中' : '已停用' }}</span>
          </div>
          <p>{{ agent.description }}</p>
          <div class="agent-card__meta">
            <span>编码：<code>{{ agent.key }}</code></span>
            <span>Graph：{{ agent.graphs }}</span>
            <span>模型：{{ agent.model }}</span>
          </div>
          <div class="agent-card__actions">
            <button type="button" class="agent-action agent-action--primary" @click.stop="openDetails(agent)">查看详情</button>
            <button type="button" class="agent-action" @click.stop="openConfig(agent)">配置入口</button>
            <RouterLink class="agent-action agent-action--link" :to="getAgentActionLinks(agent).graph">运行记录</RouterLink>
          </div>
        </div>
      </article>
    </section>

    <section class="graph-section">
      <div class="section-heading">
        <div><h2>生成报告 Graph</h2><p>点击“查看运行”进入真实运行记录和节点详情。</p></div>
        <RouterLink class="view-runs" :to="getAgentActionLinks(agents[0]).graph">查看运行记录 →</RouterLink>
      </div>
      <div class="graph-flow">
        <template v-for="(node, index) in reportGraph" :key="node.key">
          <article class="graph-node">
            <span class="graph-node__index">{{ String(index + 1).padStart(2, '0') }}</span>
            <strong>{{ node.label }}</strong>
            <small>{{ node.description }}</small>
          </article>
          <span v-if="index < reportGraph.length - 1" class="graph-arrow">→</span>
        </template>
      </div>
    </section>

    <section class="graph-section">
      <div class="section-heading">
        <div><h2>报告追问 Graph</h2><p>查看报告问答 Agent 的上下文、证据和回答链路。</p></div>
        <RouterLink class="view-runs" :to="getAgentActionLinks(agents[1]).graph">查看运行记录 →</RouterLink>
      </div>
      <div class="graph-flow graph-flow--chat">
        <template v-for="(node, index) in chatGraph" :key="node.key">
          <article class="graph-node">
            <span class="graph-node__index">{{ String(index + 1).padStart(2, '0') }}</span>
            <strong>{{ node.label }}</strong>
            <small>{{ node.description }}</small>
          </article>
          <span v-if="index < chatGraph.length - 1" class="graph-arrow">→</span>
        </template>
      </div>
    </section>

    <div v-if="selectedAgent" class="agent-drawer" @click.self="closeDrawer">
      <section class="agent-drawer__panel">
        <header class="agent-drawer__header">
          <div>
            <span class="agent-drawer__eyebrow">{{ drawerMode === 'detail' ? 'AGENT DETAIL' : 'AGENT CONFIGURATION' }}</span>
            <h2>{{ drawerTitle }}</h2>
            <p>{{ selectedAgent.name }} · <code>{{ selectedAgent.key }}</code></p>
          </div>
          <button type="button" class="drawer-close" aria-label="关闭详情" @click="closeDrawer">×</button>
        </header>

        <template v-if="drawerMode === 'detail'">
          <div class="drawer-status-row"><span class="agent-status"><i />{{ selectedAgent.status === 'active' ? '运行中' : '已停用' }}</span><span class="drawer-muted">最近运行：{{ selectedAgent.recentRun }}</span></div>
          <p class="drawer-description">{{ selectedAgent.description }}</p>
          <div class="drawer-metrics">
            <div><span>成功率</span><strong>{{ selectedAgent.successRate }}</strong></div>
            <div><span>平均耗时</span><strong>{{ selectedAgent.averageDuration }}</strong></div>
            <div><span>Token / 次</span><strong>{{ selectedAgent.tokenUsage }}</strong></div>
          </div>
          <section class="drawer-section"><h3>职责范围</h3><ul><li v-for="item in selectedAgent.responsibilities" :key="item">{{ item }}</li></ul></section>
          <section class="drawer-section"><h3>当前运行配置</h3><dl class="drawer-details"><dt>模型</dt><dd>{{ selectedAgent.model }}</dd><dt>Prompt</dt><dd>{{ selectedAgent.promptLabel }}</dd><dt>Graph</dt><dd>{{ selectedAgent.graphType }}</dd></dl></section>
          <div class="drawer-actions">
            <button type="button" class="drawer-button drawer-button--primary" @click="drawerMode = 'config'">进入配置</button>
            <RouterLink class="drawer-button" :to="selectedLinks?.graph || '/platform/graphs'">查看 Graph 运行</RouterLink>
          </div>
        </template>

        <template v-else>
          <div class="config-notice">这里展示的是当前 Agent 的真实配置入口。保存动作分别由 Prompt 中心和模型配置中心负责，不在 Agent 页面复制一套本地配置。</div>
          <div class="config-card"><div><span>Prompt 策略</span><strong>{{ selectedAgent.promptLabel }}</strong><small>查看版本、测试和发布状态</small></div><RouterLink class="drawer-button" :to="selectedLinks?.prompt || '/prompt-center'">打开 Prompt 中心</RouterLink></div>
          <div class="config-card"><div><span>模型配置</span><strong>{{ selectedAgent.model }}</strong><small>查看 Provider、模型和运行环境</small></div><RouterLink class="drawer-button" :to="selectedLinks?.model || '/infra/models'">打开模型配置</RouterLink></div>
          <div class="config-card"><div><span>执行链路</span><strong>{{ selectedAgent.graphType }}</strong><small>查看节点事件、耗时和 Trace</small></div><RouterLink class="drawer-button" :to="selectedLinks?.graph || '/platform/graphs'">打开运行记录</RouterLink></div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.agent-page { max-width: 1500px; }
.agent-page__header, .section-heading { align-items: center; display: flex; justify-content: space-between; }
.agent-page__header { margin-bottom: 24px; }
.agent-eyebrow, .agent-drawer__eyebrow { color: #7780ff; font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: .12em; margin-bottom: 9px; }
.agent-page h1 { color: var(--theme-heading); font-size: 28px; margin: 0 0 6px; }
.agent-page__header p, .section-heading p { color: var(--theme-muted); margin: 0; }
.agent-page__summary { align-items: flex-end; display: flex; flex-direction: column; gap: 12px; }
.agent-count { background: var(--theme-panel-solid); border: 1px solid var(--theme-border); border-radius: 10px; box-shadow: var(--theme-shadow-soft); color: var(--theme-heading); font-size: 12px; font-weight: 700; padding: 9px 12px; }
.agent-run-link, .view-runs { color: var(--theme-accent-strong); font-size: 12px; font-weight: 700; text-decoration: none; }
.agent-run-link:hover, .view-runs:hover { color: #fff; }
.agent-overview { display: grid; gap: 14px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-bottom: 24px; }
.agent-card { background: var(--theme-panel-solid); border: 1px solid var(--theme-border); border-radius: 14px; box-shadow: var(--theme-shadow-soft); display: flex; gap: 14px; padding: 18px; transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease; }
.agent-card:hover { border-color: var(--theme-border-strong); box-shadow: var(--theme-shadow); transform: translateY(-2px); }
.agent-card__icon { align-items: center; background: var(--theme-accent-soft); border: 1px solid var(--theme-border-strong); border-radius: 11px; color: var(--theme-accent-strong); display: flex; flex-shrink: 0; font-size: 24px; height: 44px; justify-content: center; width: 44px; }
.agent-card__body { min-width: 0; width: 100%; }
.agent-card__title { align-items: center; display: flex; gap: 10px; }
.agent-card h2 { color: var(--theme-heading); font-size: 16px; margin: 0; }
.agent-card p { color: var(--theme-muted); font-size: 12px; line-height: 1.6; margin: 7px 0 12px; }
.agent-status { align-items: center; background: var(--theme-success-soft); border-radius: 999px; color: var(--theme-success-text); display: inline-flex; font-size: 10px; gap: 5px; padding: 4px 8px; white-space: nowrap; }
.agent-status i { background: #15c78a; border-radius: 50%; height: 6px; width: 6px; }
.agent-card__meta { color: var(--theme-muted); display: flex; flex-wrap: wrap; font-size: 11px; gap: 13px; }
.agent-card__meta code, .agent-drawer p code, .drawer-details dd { color: var(--theme-accent-strong); }
.agent-card__actions { border-top: 1px solid var(--theme-border); display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; padding-top: 13px; }
.agent-action, .drawer-button { align-items: center; appearance: none; background: var(--theme-panel-soft); border: 1px solid var(--theme-border-strong); border-radius: 8px; color: var(--theme-heading); cursor: pointer; display: inline-flex; font: inherit; font-size: 11px; font-weight: 700; justify-content: center; min-height: 32px; padding: 7px 12px; text-decoration: none; transition: background .16s ease, border-color .16s ease, box-shadow .16s ease, color .16s ease, transform .16s ease; }
.agent-action:hover, .drawer-button:hover { background: var(--theme-accent-soft); border-color: var(--theme-accent); color: var(--theme-accent-strong); transform: translateY(-1px); }
.agent-action:focus-visible, .drawer-button:focus-visible, .drawer-close:focus-visible { box-shadow: 0 0 0 3px var(--theme-focus); outline: none; }
.agent-action:active, .drawer-button:active { transform: translateY(0); }
.agent-action--primary, .drawer-button--primary { background: var(--theme-accent); border-color: var(--theme-accent); color: var(--theme-accent-contrast); box-shadow: 0 5px 14px var(--theme-focus); }
.agent-action--link { align-items: center; display: inline-flex; }
.graph-section { background: var(--theme-panel-solid); border: 1px solid var(--theme-border); border-radius: 14px; box-shadow: var(--theme-shadow-soft); margin-bottom: 20px; padding: 22px; }
.section-heading { margin-bottom: 20px; }
.section-heading h2 { color: var(--theme-heading); font-size: 18px; margin: 0 0 5px; }
.graph-flow { align-items: stretch; display: flex; gap: 10px; overflow-x: auto; padding: 4px 2px 10px; }
.graph-node { background: var(--theme-gradient-soft); border: 1px solid var(--theme-border-strong); border-radius: 10px; display: flex; flex: 1 0 135px; flex-direction: column; min-height: 108px; padding: 13px; }
.graph-node__index { color: var(--theme-accent); font-family: ui-monospace, monospace; font-size: 10px; margin-bottom: 12px; }.graph-node strong { color: var(--theme-heading); font-size: 12px; }.graph-node small { color: var(--theme-muted); font-size: 10px; line-height: 1.5; margin-top: 7px; }.graph-arrow { align-self: center; color: var(--theme-accent-strong); flex: 0 0 auto; font-size: 20px; }
.agent-drawer { background: rgba(3,8,23,.68); inset: 0; position: fixed; z-index: 50; }
.agent-drawer__panel { background: var(--theme-panel-solid); border-left: 1px solid var(--theme-border); box-shadow: var(--theme-shadow); color: var(--theme-text); height: 100%; max-width: 620px; overflow: auto; padding: 28px; position: absolute; right: 0; width: 48%; }
.agent-drawer__header { align-items: flex-start; display: flex; justify-content: space-between; }.agent-drawer__header h2 { color: var(--theme-heading); font-size: 22px; margin: 0 0 6px; }.agent-drawer__header p { color: var(--theme-muted); font-size: 12px; margin: 0; }.drawer-close { background: transparent; border: 0; color: var(--theme-muted); cursor: pointer; font-size: 28px; line-height: 1; }.drawer-close:hover { color: var(--theme-heading); }
.drawer-status-row { align-items: center; display: flex; gap: 12px; margin: 28px 0 12px; }.drawer-muted { color: var(--theme-muted); font-size: 11px; }.drawer-description { color: var(--theme-text); font-size: 13px; line-height: 1.7; }
.drawer-metrics { display: grid; gap: 8px; grid-template-columns: repeat(3, 1fr); margin: 22px 0; }.drawer-metrics div, .config-card { background: var(--theme-panel-soft); border: 1px solid var(--theme-border); border-radius: 9px; padding: 13px; }.drawer-metrics span, .config-card span, .config-card small { color: var(--theme-muted); display: block; font-size: 10px; }.drawer-metrics strong { color: var(--theme-heading); display: block; font-size: 16px; margin-top: 7px; }
.drawer-section { border-top: 1px solid var(--theme-border); margin-top: 20px; padding-top: 18px; }.drawer-section h3 { color: var(--theme-heading); font-size: 13px; margin: 0 0 12px; }.drawer-section ul { color: var(--theme-text); font-size: 12px; line-height: 1.8; margin: 0; padding-left: 18px; }.drawer-details { display: grid; gap: 10px 18px; grid-template-columns: 90px 1fr; margin: 0; }.drawer-details dt { color: var(--theme-muted); font-size: 12px; }.drawer-details dd { font-size: 12px; margin: 0; overflow-wrap: anywhere; }
.drawer-actions { display: flex; gap: 8px; margin-top: 24px; }.config-notice { background: var(--theme-accent-soft); border-left: 3px solid var(--theme-accent); color: var(--theme-text); font-size: 12px; line-height: 1.7; margin: 25px 0 14px; padding: 11px 13px; }.config-card { align-items: center; display: flex; justify-content: space-between; gap: 14px; margin-top: 10px; }.config-card strong { color: var(--theme-heading); display: block; font-size: 13px; margin: 5px 0; }.config-card small { line-height: 1.5; }
@media (max-width: 900px) { .agent-overview { grid-template-columns: 1fr; }.agent-page__header { align-items: flex-start; flex-direction: column; gap: 16px; }.agent-page__summary { align-items: flex-start; }.section-heading { align-items: flex-start; flex-direction: column; gap: 10px; }.agent-drawer__panel { max-width: none; width: 86%; } }
@media (max-width: 560px) { .agent-card { flex-direction: column; }.drawer-metrics { grid-template-columns: 1fr; }.config-card { align-items: flex-start; flex-direction: column; }.drawer-actions { flex-direction: column; } }
</style>
