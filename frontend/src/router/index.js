import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', redirect: '/dashboard/graph' },
  {
    path: '/login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard/graph' },
      { path: 'graph',       component: () => import('../views/KnowledgeGraph.vue') },
      { path: 'predictions', component: () => import('../views/PredictionReport.vue') },
      { path: 'velocity',    component: () => import('../views/VelocityChart.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isValid) {
    next('/login')
  } else {
    next()
  }
})

export default router
