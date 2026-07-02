import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/pages/HomePage.vue'),
      meta: {
        title: '智能运营中心 AI Agent',
      },
    },
    {
      path: '/items',
      name: 'items',
      component: () => import('@/pages/ItemManagePage.vue'),
      meta: {
        title: '数据管理 - 智能运营中心',
      },
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
