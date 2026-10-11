import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import type { Role } from '@/api/types'
import CabinetLayout from '@/layouts/CabinetLayout.vue'
import PublicLayout from '@/layouts/PublicLayout.vue'
import { useAuthStore } from '@/stores/auth'
import { useReferenceStore } from '@/stores/reference'

// Route meta (read with metaRole / metaFlag below; RouteMeta is not augmented to keep `type`-only code):
//   role      'candidate' | 'employer'  - the page needs this role
//   guestOnly true                       - logged-in users are sent to their cabinet
//   title     string                     - document title prefix

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: PublicLayout,
    children: [
      { path: '', name: 'landing', component: () => import('@/pages/Landing.vue'), meta: { title: 'Главная' } },
      {
        path: 'login',
        name: 'login',
        component: () => import('@/pages/Login.vue'),
        meta: { title: 'Вход', guestOnly: true },
      },
      {
        path: 'register',
        name: 'register',
        component: () => import('@/pages/Register.vue'),
        meta: { title: 'Регистрация', guestOnly: true },
      },
      {
        path: 'privacy',
        name: 'privacy',
        component: () => import('@/pages/Privacy.vue'),
        meta: { title: 'Приватность и данные' },
      },
    ],
  },
  {
    path: '/candidate',
    component: CabinetLayout,
    meta: { role: 'candidate' },
    children: [
      {
        path: '',
        name: 'candidate-overview',
        component: () => import('@/pages/candidate/Overview.vue'),
        meta: { title: 'Обзор' },
      },
      {
        path: 'profile',
        name: 'candidate-profile',
        component: () => import('@/pages/candidate/Profile.vue'),
        meta: { title: 'Анкета' },
      },
      {
        path: 'fsp',
        name: 'candidate-fsp',
        component: () => import('@/pages/candidate/Fsp.vue'),
        meta: { title: 'Привязка к ФСП' },
      },
      {
        path: 'tests',
        name: 'candidate-tests',
        component: () => import('@/pages/candidate/Tests.vue'),
        meta: { title: 'Экспресс-тесты' },
      },
      {
        path: 'offers',
        name: 'candidate-offers',
        component: () => import('@/pages/candidate/Offers.vue'),
        meta: { title: 'Офферы' },
      },
    ],
  },
  {
    path: '/employer',
    component: CabinetLayout,
    meta: { role: 'employer' },
    children: [
      {
        path: '',
        name: 'employer-dashboard',
        component: () => import('@/pages/employer/Dashboard.vue'),
        meta: { title: 'Витрина категорий' },
      },
      {
        path: 'search',
        name: 'employer-search',
        component: () => import('@/pages/employer/Search.vue'),
        meta: { title: 'Поиск кандидатов' },
      },
      {
        path: 'candidates/:id(\\d+)',
        name: 'employer-candidate',
        component: () => import('@/pages/employer/CandidateCard.vue'),
        meta: { title: 'Карточка кандидата' },
      },
      {
        path: 'vacancies',
        name: 'employer-vacancies',
        component: () => import('@/pages/employer/Vacancies.vue'),
        meta: { title: 'Вакансии' },
      },
      {
        path: 'offers',
        name: 'employer-offers',
        component: () => import('@/pages/employer/Offers.vue'),
        meta: { title: 'Офферы' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    component: PublicLayout,
    children: [
      { path: '', name: 'not-found', component: () => import('@/pages/NotFound.vue'), meta: { title: 'Страница не найдена' } },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition !== null) {
      return savedPosition
    }
    if (to.hash !== '') {
      return { el: to.hash, top: 80, behavior: 'smooth' }
    }
    // Same page, different query (filters, pagination): keep the scroll position.
    if (to.path === from.path) {
      return false
    }
    return { top: 0 }
  },
})

function metaRole(value: unknown): Role | null {
  return value === 'candidate' || value === 'employer' ? value : null
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.restore()

  const requiredRole = metaRole(to.meta.role)
  if (requiredRole !== null) {
    if (!auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    if (auth.role !== requiredRole) {
      // Wrong cabinet: send the user to their own.
      return { path: auth.homePath }
    }
    // Cabinet pages rely on dictionaries (skills, cities, titles): load them once before the first render.
    await useReferenceStore().load()
    return true
  }

  if (to.meta.guestOnly === true && auth.isAuthenticated) {
    return { path: auth.homePath }
  }
  return true
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title === '' ? 'ФСП.Карьера' : `${title} · ФСП.Карьера`
})
