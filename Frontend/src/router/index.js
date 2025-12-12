import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import CameraView from '../views/CameraView.vue'
import AdminView from '../views/AdminView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'login', component: LoginView, meta: { requiresGuest: true } },
    { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { requiresAuth: true } },
    { path: '/camera/:id', name: 'camera', component: CameraView, meta: { requiresAuth: true } },
    { path: '/admin', name: 'admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } }
  ],
})

router.beforeEach((to, from, next) => {
  const u = localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')) : null
  if (to.meta.requiresAuth && !u) next('/login')
  else if (to.meta.requiresGuest && u) next('/dashboard')
  else if (to.meta.requiresAdmin && (!u || !u.is_admin)) next('/dashboard')
  else next()
})

export default router