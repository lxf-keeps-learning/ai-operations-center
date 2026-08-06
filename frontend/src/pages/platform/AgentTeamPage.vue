<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  buildTeamDetails,
  getRouteLinks,
  getTeamMemberLinks,
  type DomainRoute,
  type TeamMember,
  type TeamNode,
} from './agentTeamPageModel'

type DrawerMode = 'node' | 'member' | 'route'

const team = buildTeamDetails()
const selectedNode = ref<TeamNode | null>(null)
const selectedMember = ref<TeamMember | null>(null)
const selectedRoute = ref<DomainRoute | null>(null)
const drawerMode = ref<DrawerMode>('node')
const drawerTitle = computed(() => ({ node: '节点详情', member: '成员详情', route: '路由配置' })[drawerMode.value])
const selectedMemberLinks = computed(() => selectedMember.value ? getTeamMemberLinks(selectedMember.value) : null)
const selectedRouteLinks = computed(() => selectedRoute.value ? getRouteLinks(selectedRoute.value) : null)

function openNode(node: TeamNode) {
  selectedNode.value = node
  selectedMember.value = null
  selectedRoute.value = null
  drawerMode.value = 'node'
}

function openMember(member: TeamMember) {
  selectedMember.value = member
  selectedNode.value = null
  selectedRoute.value = null
  drawerMode.value = 'member'
}

function openRoute(route: DomainRoute) {
  selectedRoute.value = route
  selectedNode.value = null
  selectedMember.value = null
  drawerMode.value = 'route'
}

function closeDrawer() {
  selectedNode.value = null
  selectedMember.value = null
  selectedRoute.value = null
}
</script>

<template>
  <div class="team-page">
    <header class="team-header">
      <div>
        <div class="team-eyebrow">AGENT TEAM / SUPERVISOR GRAPH</div>
        <h1>运营分析 Team</h1>
        <p>查看 Team 编排、节点职责、成员 Agent 和业务域路由配置。</p>
      </div>
      <div class="team-header__actions">
        <span class="team-status"><i />运行中</span>
        <RouterLink class="team-run-link" :to="`/platform/graphs?type=report_generation`">查看运行记录 →</RouterLink>
      </div>
    </header>

    <section class="team-summary">
      <div><span>Team 编码</span><strong>{{ team.code }}</strong></div>
      <div><span>执行 Graph</span><strong>{{ team.graph }}</strong></div>
      <div><span>成员 Agent</span><strong>{{ team.members.length }} 个</strong></div>
      <div><span>路由领域</span><strong>{{ team.routes.length }} 个</strong></div>
    </section>

    <section class="team-section">
      <div class="section-title"><div><h2>Team 执行拓扑</h2><p>点击任意节点查看输入、输出和职责。</p></div><span class="section-badge">Supervisor Orchestration</span></div>
      <div class="team-flow">
        <template v-for="(node, index) in team.nodes" :key="node.key">
          <button type="button" class="team-flow__node" :class="`team-flow__node--${node.tone}`" @click="openNode(node)">
            <span>0{{ index + 1 }}</span><strong>{{ node.label }}</strong><small>{{ node.caption }}</small><em>查看节点 →</em>
          </button>
          <b v-if="index < team.nodes.length - 1">→</b>
        </template>
      </div>
      <div class="team-flow__note">领域 Agent 会根据 Supervisor 的路由结果进入对应分支；每次执行都会记录 Session、Trace 和 Graph 运行事件。</div>
    </section>

    <div class="team-columns">
      <section class="team-section team-section--members">
        <div class="section-title"><div><h2>Team 成员</h2><p>点击成员查看职责和关联运行记录。</p></div></div>
        <div class="member-list">
          <article v-for="member in team.members" :key="member.key" class="member" @click="openMember(member)">
            <div class="member__avatar">♙</div>
            <div class="member__content"><strong>{{ member.name }}</strong><p>{{ member.role }}</p><small>{{ member.key }}</small></div>
            <span class="member__status"><i />已启用</span>
            <span class="member__arrow">→</span>
          </article>
        </div>
      </section>

      <section class="team-section">
        <div class="section-title"><div><h2>Supervisor 路由</h2><p>点击路由查看目标 Agent 和 Prompt。</p></div></div>
        <div class="route-list">
          <button v-for="route in team.routes" :key="route.key" type="button" class="route-item" @click="openRoute(route)">
            <span>{{ route.label }}</span><code>{{ route.key }}</code><small>{{ route.desc }}</small><em>{{ route.targetAgent }} · 配置 →</em>
          </button>
        </div>
      </section>
    </div>

    <div v-if="selectedNode || selectedMember || selectedRoute" class="team-drawer" @click.self="closeDrawer">
      <section class="team-drawer__panel">
        <header class="team-drawer__header">
          <div><span class="team-drawer__eyebrow">TEAM {{ drawerMode.toUpperCase() }}</span><h2>{{ drawerTitle }}</h2><p v-if="selectedNode">{{ selectedNode.label }} · <code>{{ selectedNode.key }}</code></p><p v-else-if="selectedMember">{{ selectedMember.name }} · <code>{{ selectedMember.key }}</code></p><p v-else>{{ selectedRoute?.label }} · <code>{{ selectedRoute?.key }}</code></p></div>
          <button type="button" class="drawer-close" aria-label="关闭详情" @click="closeDrawer">×</button>
        </header>

        <template v-if="selectedNode">
          <div class="drawer-hero"><span class="drawer-kicker">执行节点</span><strong>{{ selectedNode.label }}</strong><p>{{ selectedNode.detail }}</p></div>
          <dl class="drawer-details"><dt>输入</dt><dd>{{ selectedNode.input }}</dd><dt>输出</dt><dd>{{ selectedNode.output }}</dd><dt>所属 Graph</dt><dd>{{ team.graph }}</dd></dl>
          <div class="drawer-actions"><RouterLink class="drawer-button drawer-button--primary" to="/platform/graphs?type=report_generation">查看运行记录</RouterLink><RouterLink class="drawer-button" to="/platform/traces">查看 Trace</RouterLink></div>
        </template>

        <template v-else-if="selectedMember">
          <div class="drawer-hero"><span class="drawer-kicker">Team 成员</span><strong>{{ selectedMember.name }}</strong><p>{{ selectedMember.detail }}</p></div>
          <div class="drawer-status"><span class="team-status"><i />{{ selectedMember.status === 'active' ? '已启用' : '已停用' }}</span><span>{{ selectedMember.role }}</span></div>
          <dl class="drawer-details"><dt>Agent</dt><dd>{{ selectedMember.agentKey }}</dd><dt>Graph</dt><dd>{{ selectedMember.graphType }}</dd><dt>状态</dt><dd>正常</dd></dl>
          <div class="drawer-actions"><RouterLink class="drawer-button drawer-button--primary" :to="selectedMemberLinks?.agent || '/platform/agents'">查看 Agent</RouterLink><RouterLink class="drawer-button" :to="selectedMemberLinks?.graph || '/platform/graphs'">查看运行</RouterLink></div>
        </template>

        <template v-else-if="selectedRoute">
          <div class="drawer-hero"><span class="drawer-kicker">业务域路由</span><strong>{{ selectedRoute.label }}</strong><p>{{ selectedRoute.desc }}</p></div>
          <dl class="drawer-details"><dt>目标 Agent</dt><dd>{{ selectedRoute.targetAgent }}</dd><dt>Prompt</dt><dd>{{ selectedRoute.promptLabel }}</dd><dt>优先级</dt><dd>P{{ selectedRoute.priority }}</dd></dl>
          <div class="route-config-note">路由保存由后续 Team 配置服务负责；当前入口直接进入已有 Agent、Prompt 和 Graph 页面，避免在展示页做无效的本地保存。</div>
          <div class="drawer-actions"><RouterLink class="drawer-button drawer-button--primary" :to="selectedRouteLinks?.agent || '/platform/agents'">查看目标 Agent</RouterLink><RouterLink class="drawer-button" :to="selectedRouteLinks?.prompt || '/prompt-center'">查看 Prompt</RouterLink><RouterLink class="drawer-button" :to="selectedRouteLinks?.graph || '/platform/graphs'">查看运行</RouterLink></div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.team-page { max-width: 1500px; }.team-header { align-items: flex-start; display: flex; justify-content: space-between; margin-bottom: 22px; }.team-eyebrow, .team-drawer__eyebrow { color: var(--theme-accent-strong); font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: .12em; margin-bottom: 10px; }.team-header h1 { color: var(--theme-heading); font-size: 28px; margin: 0 0 6px; }.team-header p { color: var(--theme-muted); margin: 0; }.team-header__actions { align-items: flex-end; display: flex; flex-direction: column; gap: 14px; }.team-status { align-items: center; background: var(--theme-success-soft); border-radius: 999px; color: var(--theme-success-text); display: inline-flex; font-size: 11px; gap: 6px; padding: 7px 10px; }.team-status i { background: #15c78a; border-radius: 50%; height: 6px; width: 6px; }.team-run-link { color: var(--theme-accent-strong); font-size: 12px; font-weight: 700; text-decoration: none; }.team-summary { background: var(--theme-panel-solid); border: 1px solid var(--theme-border); border-radius: 12px; box-shadow: var(--theme-shadow-soft); display: grid; grid-template-columns: repeat(4, 1fr); margin-bottom: 20px; }.team-summary div { border-right: 1px solid var(--theme-border); padding: 17px 20px; }.team-summary div:last-child { border-right: 0; }.team-summary span, .team-summary strong { display: block; }.team-summary span { color: var(--theme-muted); font-size: 11px; margin-bottom: 7px; }.team-summary strong { color: var(--theme-heading); font-family: ui-monospace, monospace; font-size: 13px; overflow-wrap: anywhere; }.team-section { background: var(--theme-panel-solid); border: 1px solid var(--theme-border); border-radius: 14px; box-shadow: var(--theme-shadow-soft); margin-bottom: 20px; padding: 22px; }.section-title { align-items: center; display: flex; justify-content: space-between; margin-bottom: 20px; }.section-title h2 { color: var(--theme-heading); font-size: 17px; margin: 0 0 5px; }.section-title p { color: var(--theme-muted); font-size: 12px; margin: 0; }.section-badge { color: var(--theme-accent-strong); font-size: 11px; font-weight: 700; }.team-flow { align-items: stretch; display: flex; gap: 10px; overflow-x: auto; }.team-flow__node { background: var(--theme-gradient-soft); border: 1px solid var(--theme-border-strong); border-radius: 10px; cursor: pointer; display: flex; flex: 1 0 150px; flex-direction: column; min-height: 122px; padding: 14px; text-align: left; transition: box-shadow .16s ease, transform .16s ease; }.team-flow__node:hover { box-shadow: var(--theme-shadow-soft); transform: translateY(-2px); }.team-flow__node > span { color: var(--theme-accent); font-family: ui-monospace, monospace; font-size: 10px; margin-bottom: 13px; }.team-flow__node strong { color: var(--theme-heading); font-size: 12px; }.team-flow__node small { color: var(--theme-muted); font-size: 10px; line-height: 1.5; margin-top: 7px; }.team-flow__node em { color: var(--theme-accent-strong); font-size: 10px; font-style: normal; font-weight: 700; margin-top: auto; padding-top: 9px; }.team-flow b { align-self: center; color: var(--theme-accent-strong); font-size: 20px; }.team-flow__note { background: var(--theme-accent-soft); border-left: 3px solid var(--theme-accent); color: var(--theme-text); font-size: 11px; line-height: 1.6; margin-top: 18px; padding: 9px 12px; }.team-columns { display: grid; gap: 20px; grid-template-columns: 1.1fr .9fr; }.team-section--members { margin-bottom: 0; }.member-list, .route-list { display: grid; gap: 8px; }.member, .route-item { background: var(--theme-panel-soft); border: 1px solid var(--theme-border); border-radius: 9px; }.member { align-items: center; cursor: pointer; display: flex; gap: 11px; padding: 11px; transition: border-color .16s ease, transform .16s ease, box-shadow .16s ease; }.member:hover, .route-item:hover { border-color: var(--theme-border-strong); box-shadow: var(--theme-shadow-soft); transform: translateY(-1px); }.member__avatar { align-items: center; background: var(--theme-accent-soft); border: 1px solid var(--theme-border-strong); border-radius: 7px; color: var(--theme-accent-strong); display: flex; height: 31px; justify-content: center; width: 31px; }.member__content { min-width: 0; }.member strong { color: var(--theme-heading); font-size: 12px; }.member p, .member small { color: var(--theme-muted); display: block; font-size: 11px; margin: 4px 0 0; }.member small { font-family: ui-monospace, monospace; font-size: 10px; }.member__status { align-items: center; color: var(--theme-success-text); display: inline-flex; font-size: 10px; gap: 5px; margin-left: auto; white-space: nowrap; }.member__status i { background: #15c78a; border-radius: 50%; height: 6px; width: 6px; }.member__arrow { color: var(--theme-accent-strong); font-size: 15px; }.route-item { cursor: pointer; display: grid; gap: 5px; grid-template-columns: 1fr auto; padding: 12px; text-align: left; width: 100%; }.route-item span { color: var(--theme-heading); font-size: 12px; font-weight: 700; }.route-item code { color: var(--theme-accent-strong); font-size: 10px; }.route-item small, .route-item em { color: var(--theme-muted); font-size: 10px; font-style: normal; grid-column: 1 / -1; }.route-item em { color: var(--theme-accent-strong); font-weight: 700; }
.team-drawer { background: rgba(15, 23, 42, .42); inset: 0; position: fixed; z-index: 50; }.team-drawer__panel { background: var(--theme-panel-solid); border-left: 1px solid var(--theme-border); box-shadow: var(--theme-shadow); color: var(--theme-text); height: 100%; max-width: 620px; overflow: auto; padding: 28px; position: absolute; right: 0; width: 48%; }.team-drawer__header { align-items: flex-start; display: flex; justify-content: space-between; }.team-drawer__header h2 { color: var(--theme-heading); font-size: 22px; margin: 0 0 6px; }.team-drawer__header p { color: var(--theme-muted); font-size: 12px; margin: 0; }.team-drawer__header code { color: var(--theme-accent-strong); }.drawer-close { background: transparent; border: 0; color: var(--theme-muted); cursor: pointer; font-size: 28px; line-height: 1; }.drawer-close:hover { color: var(--theme-heading); }.drawer-hero { background: var(--theme-gradient-soft); border: 1px solid var(--theme-border-strong); border-radius: 11px; margin: 26px 0 18px; padding: 16px; }.drawer-kicker { color: var(--theme-accent-strong); display: block; font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }.drawer-hero strong { color: var(--theme-heading); display: block; font-size: 20px; margin: 7px 0; }.drawer-hero p { color: var(--theme-text); font-size: 13px; line-height: 1.7; margin: 0; }.drawer-status { align-items: center; color: var(--theme-muted); display: flex; gap: 12px; margin: 18px 0; }.drawer-details { display: grid; gap: 12px 18px; grid-template-columns: 90px 1fr; margin: 20px 0; }.drawer-details dt { color: var(--theme-muted); font-size: 12px; }.drawer-details dd { color: var(--theme-heading); font-size: 12px; margin: 0; overflow-wrap: anywhere; }.drawer-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 24px; }.drawer-button { align-items: center; appearance: none; background: var(--theme-panel-soft); border: 1px solid var(--theme-border-strong); border-radius: 8px; color: var(--theme-heading); display: inline-flex; font-size: 11px; font-weight: 700; min-height: 32px; padding: 7px 12px; text-decoration: none; }.drawer-button:hover { background: var(--theme-accent-soft); color: var(--theme-accent-strong); }.drawer-button--primary { background: var(--theme-accent); border-color: var(--theme-accent); color: var(--theme-accent-contrast); }.route-config-note { background: var(--theme-warning-soft); border-left: 3px solid #f59e0b; color: var(--theme-text); font-size: 12px; line-height: 1.7; margin-top: 24px; padding: 11px 13px; }
@media (max-width: 900px) { .team-header { flex-direction: column; gap: 16px; }.team-header__actions { align-items: flex-start; }.team-summary { grid-template-columns: repeat(2, 1fr); }.team-summary div:nth-child(2) { border-right: 0; }.team-columns { grid-template-columns: 1fr; }.team-drawer__panel { max-width: none; width: 86%; } }
@media (max-width: 560px) { .team-summary { grid-template-columns: 1fr; }.team-summary div { border-bottom: 1px solid var(--theme-border); border-right: 0; }.team-summary div:last-child { border-bottom: 0; }.drawer-actions { flex-direction: column; } }
</style>
