import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/',
    component: () => import('../views/LandingPage.vue'),
  },
  {
    // Legacy token-paste login kept for developer use
    path: '/login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '',            redirect: '/dashboard/graph' },
      { path: 'graph',       component: () => import('../views/KnowledgeGraph.vue') },
      { path: 'predictions', component: () => import('../views/PredictionReport.vue') },
      { path: 'velocity',    component: () => import('../views/VelocityChart.vue') },
      { path: 'admin',       component: () => import('../views/AdminPanel.vue'),  meta: { requiresAdmin: true } },
      { path: 'upload',      component: () => import('../views/UploadView.vue') },
      { path: 'simulation',  component: () => import('../views/SimulationView.vue') },
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
    next('/')
  } else if (to.meta.requiresAdmin && !auth.isAdmin) {
    next('/dashboard/graph')
  } else {
    next()
  }
})

export default router
