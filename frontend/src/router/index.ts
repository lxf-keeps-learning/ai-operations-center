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
      path: '/items',
      name: 'items',
      component: () => import('@/pages/ItemManagePage.vue'),
      meta: { title: '数据管理 - 智能运营中心' },
    },
    {
      path: '/infra',
      name: 'infra-dashboard',
      component: () => import('@/pages/dashboard/IndexPage.vue'),
      meta: { title: '基础设施控制台 - 智能运营中心' },
    },
    {
      path: '/infra/config',
      name: 'infra-config',
      component: () => import('@/pages/config-center/IndexPage.vue'),
      meta: { title: '配置中心 - 智能运营中心' },
    },
    {
      path: '/infra/models',
      name: 'infra-models',
      component: () => import('@/pages/model-config/IndexPage.vue'),
      meta: { title: '模型配置 - 智能运营中心' },
    },
    {
      path: '/infra/logs',
      name: 'infra-logs',
      component: () => import('@/pages/log-center/IndexPage.vue'),
      meta: { title: '日志中心 - 智能运营中心' },
    },
    {
      path: '/infra/trace',
      name: 'infra-trace',
      component: () => import('@/pages/trace-viewer/IndexPage.vue'),
      meta: { title: 'Trace 查询 - 智能运营中心' },
    },
    {
      path: '/infra/errors',
      name: 'infra-errors',
      component: () => import('@/pages/error-code/IndexPage.vue'),
      meta: { title: '错误码说明 - 智能运营中心' },
    },
    {
      path: '/infra/health',
      name: 'infra-health',
      component: () => import('@/pages/health-check/IndexPage.vue'),
      meta: { title: '健康检查 - 智能运营中心' },
    },
    {
      path: '/infra/context',
      name: 'infra-context',
      component: () => import('@/pages/context-demo/IndexPage.vue'),
      meta: { title: 'Context 示例 - 智能运营中心' },
    },
    {
      path: '/operation',
      name: 'operation',
      component: () => import('@/pages/operation/IndexPage.vue'),
      meta: { title: '运营分析 - 智能运营中心' },
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
