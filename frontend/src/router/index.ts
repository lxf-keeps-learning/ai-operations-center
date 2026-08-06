import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/pages/HomePage.vue'),
      meta: { title: '智能运营中心 AI Agent' },
    },
    {
      path: '/platform',
      name: 'platform-dashboard',
      component: () => import('@/pages/platform/IndexPage.vue'),
      meta: { title: 'Agent 平台概览 - 智能运营中心', platform: true },
    },
    {
      path: '/platform/sessions',
      name: 'platform-sessions',
      component: () => import('@/pages/platform/SessionListPage.vue'),
      meta: { title: 'Session - 智能运营中心', platform: true },
    },
    {
      path: '/platform/operation-inbox',
      name: 'platform-operation-inbox',
      component: () => import('@/pages/platform/OperationInboxPage.vue'),
      meta: { title: '待处理消息 - 智能运营中心', platform: true },
    },
    {
      path: '/platform/messages',
      name: 'platform-messages',
      component: () => import('@/pages/platform/MessageInboxPage.vue'),
      meta: { title: '待处理消息 - 智能运营中心', platform: true },
    },
    {
      path: '/platform/conversations',
      name: 'platform-conversations',
      component: () => import('@/pages/platform/ConversationPage.vue'),
      meta: { title: '对话工作台 - 智能运营中心', platform: true },
    },
    {
      path: '/platform/traces',
      name: 'platform-traces',
      component: () => import('@/pages/platform/TraceListPage.vue'),
      meta: { title: 'Trace 链路 - 智能运营中心', platform: true },
    },
    {
      path: '/platform/graphs',
      name: 'platform-graphs',
      component: () => import('@/pages/platform/GraphRunsPage.vue'),
      meta: { title: 'Graph 运行记录 - 智能运营中心', platform: true },
    },
    {
      path: '/platform/agents',
      name: 'platform-agents',
      component: () => import('@/pages/platform/AgentPage.vue'),
      meta: { title: 'Agent - 智能运营中心', platform: true },
    },
    {
      path: '/platform/teams',
      name: 'platform-teams',
      component: () => import('@/pages/platform/AgentTeamPage.vue'),
      meta: { title: 'Agent Team - 智能运营中心', platform: true },
    },
    {
      path: '/items',
      name: 'items',
      component: () => import('@/pages/ItemManagePage.vue'),
      meta: { title: '数据管理 - 智能运营中心' },
    },
    {
      path: '/infra',
      name: 'infra-dashboard',
      redirect: '/platform',
      meta: { title: 'Agent 平台概览 - 智能运营中心', platform: true },
    },
    {
      path: '/infra/config',
      name: 'infra-config',
      component: () => import('@/pages/config-center/IndexPage.vue'),
      meta: { title: '配置中心 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/infra/models',
      name: 'infra-models',
      component: () => import('@/pages/model-config/IndexPage.vue'),
      meta: { title: '模型配置 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/infra/logs',
      name: 'infra-logs',
      component: () => import('@/pages/log-center/IndexPage.vue'),
      meta: { title: '日志中心 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/infra/trace',
      name: 'infra-trace',
      redirect: '/platform/traces',
      meta: { title: 'Trace 链路 - 智能运营中心', platform: true },
    },
    {
      path: '/infra/errors',
      name: 'infra-errors',
      component: () => import('@/pages/error-code/IndexPage.vue'),
      meta: { title: '错误码说明 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/infra/health',
      name: 'infra-health',
      component: () => import('@/pages/health-check/IndexPage.vue'),
      meta: { title: '健康检查 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/infra/context',
      name: 'infra-context',
      component: () => import('@/pages/context-demo/IndexPage.vue'),
      meta: { title: 'Context 示例 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/operation',
      name: 'operation',
      component: () => import('@/pages/operation/IndexPage.vue'),
      meta: { title: '报告分析 - 智能运营中心' },
    },
    {
      path: '/operation/records',
      redirect: '/operation',
    },
    {
      path: '/operation/report-chat',
      redirect: '/operation',
    },
    {
      path: '/prompt-center',
      name: 'prompt-center',
      component: () => import('@/views/prompt-center/PromptList.vue'),
      meta: { title: 'AI 策略与 Prompt 管理 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/prompt-center/:id',
      name: 'prompt-detail',
      component: () => import('@/views/prompt-center/PromptDetail.vue'),
      meta: { title: 'Prompt 详情 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/prompt-center/:id/edit',
      name: 'prompt-editor',
      component: () => import('@/views/prompt-center/PromptEditor.vue'),
      meta: { title: '编辑 Prompt - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/prompt-center/:id/test',
      name: 'prompt-test',
      component: () => import('@/views/prompt-center/PromptTest.vue'),
      meta: { title: 'Prompt 测试 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/prompt-center/:id/compare',
      name: 'prompt-compare',
      component: () => import('@/views/prompt-center/PromptCompare.vue'),
      meta: { title: '版本对比 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/prompt-center/:id/release',
      name: 'prompt-release',
      component: () => import('@/views/prompt-center/PromptRelease.vue'),
      meta: { title: 'Prompt 发布 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/prompt-center/:id/metrics',
      name: 'prompt-metrics',
      component: () => import('@/views/prompt-center/PromptMetrics.vue'),
      meta: { title: 'Prompt 指标 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/evaluation',
      name: 'evaluation',
      component: () => import('@/views/evaluation-center/PromptQualityPage.vue'),
      meta: { title: 'Prompt 质量评估 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/experiments',
      name: 'experiments',
      component: () => import('@/views/experiment-center/ExperimentList.vue'),
      meta: { title: '实验中心 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/experiments/create',
      name: 'experiment-create',
      component: () => import('@/views/experiment-center/ExperimentCreate.vue'),
      meta: { title: '创建实验 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/experiments/:id/compare',
      name: 'experiment-compare',
      component: () => import('@/views/experiment-center/ExperimentCompare.vue'),
      meta: { title: '实验对比 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/failures',
      name: 'failures',
      component: () => import('@/views/failure-center/FailureList.vue'),
      meta: { title: '失败案例 - 智能运营中心', platform: true, platformLegacy: true },
    },
    {
      path: '/failures/:id',
      name: 'failure-detail',
      component: () => import('@/views/failure-center/FailureDetail.vue'),
      meta: { title: '失败案例详情 - 智能运营中心', platform: true, platformLegacy: true },
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

router.afterEach((to) => {
  document.title = typeof to.meta.title === 'string' ? to.meta.title : '智能运营中心 AI Agent'
})

export default router
