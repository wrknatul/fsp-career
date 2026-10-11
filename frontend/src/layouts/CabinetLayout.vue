<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import type { Role } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppLogo from '@/components/AppLogo.vue'
import DemoBanner from '@/components/DemoBanner.vue'
import { useAuthStore } from '@/stores/auth'
import { useInboxStore } from '@/stores/inbox'
import { useToastStore } from '@/stores/toast'

// Layout of both cabinets. The router guard guarantees a logged-in user with the matching role.
type NavItem = {
  to: string
  label: string
  /** Active only on the exact path (cabinet roots). */
  exact?: boolean
  /** Extra path prefixes that also highlight this tab. */
  also?: string[]
  badge?: number
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const inbox = useInboxStore()
const toast = useToastStore()

const ROLE_TITLES: Record<Role, string> = { candidate: 'Соискатель', employer: 'Работодатель' }

const nav = computed<NavItem[]>(() => {
  if (auth.role === 'employer') {
    return [
      { to: '/employer', label: 'Витрина', exact: true },
      { to: '/employer/search', label: 'Поиск', also: ['/employer/candidates'] },
      { to: '/employer/vacancies', label: 'Вакансии' },
      { to: '/employer/offers', label: 'Офферы' },
    ]
  }
  return [
    { to: '/candidate', label: 'Обзор', exact: true },
    { to: '/candidate/profile', label: 'Анкета' },
    { to: '/candidate/fsp', label: 'ФСП' },
    { to: '/candidate/tests', label: 'Тесты' },
    { to: '/candidate/offers', label: 'Офферы', badge: inbox.pendingOffers },
  ]
})

function isActive(item: NavItem): boolean {
  const path = route.path
  if (item.exact) {
    return path === item.to
  }
  const prefixes = [item.to, ...(item.also ?? [])]
  return prefixes.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))
}

const initials = computed(() =>
  auth.displayName
    .split(/\s+/)
    .filter((part) => part !== '')
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join(''),
)

function logout(): void {
  auth.logout()
  inbox.reset()
  toast.info('Вы вышли из аккаунта')
  void router.push({ name: 'landing' })
}

function focusMain(): void {
  document.getElementById('main')?.focus()
}

onMounted(() => {
  if (auth.role === 'candidate') {
    void inbox.refresh()
  }
})
</script>

<template>
  <div class="shell">
    <a href="#main" class="skip-link" @click.prevent="focusMain">К содержимому</a>
    <DemoBanner />

    <header class="topbar">
      <div class="container topbar__inner">
        <AppLogo :to="auth.homePath" />

        <nav class="nav" aria-label="Разделы кабинета">
          <RouterLink
            v-for="item in nav"
            :key="item.to"
            :to="item.to"
            class="nav__link"
            :class="{ 'is-active': isActive(item) }"
            :aria-current="isActive(item) ? 'page' : undefined"
          >
            {{ item.label }}
            <span v-if="item.badge" class="nav__badge num" :aria-label="`${item.badge} новых`">{{ item.badge }}</span>
          </RouterLink>
        </nav>

        <div class="user">
          <span class="user__avatar num" aria-hidden="true">{{ initials }}</span>
          <span class="user__text">
            <span class="user__name truncate">{{ auth.displayName }}</span>
            <span class="user__role">{{ auth.role ? ROLE_TITLES[auth.role] : '' }}</span>
          </span>
          <AppButton variant="ghost" size="sm" aria-label="Выйти" @click="logout">
            <AppIcon name="logout" :size="16" />
            <span class="user__logout-text">Выйти</span>
          </AppButton>
        </div>
      </div>
    </header>

    <main id="main" class="container page shell__main" tabindex="-1">
      <RouterView v-slot="{ Component, route: current }">
        <component :is="Component" :key="current.path" />
      </RouterView>
    </main>

    <footer class="foot">
      <div class="container foot__inner">
        <span>ФСП.Карьера · демо-стенд, данные вымышлены</span>
        <RouterLink :to="{ name: 'privacy' }">Приватность и данные</RouterLink>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
.shell__main {
  flex: 1;
  width: 100%;
  outline: none;
}
.skip-link {
  position: absolute;
  left: 12px;
  top: -60px;
  z-index: 300;
  padding: 10px 16px;
  border-radius: var(--r-md);
  background: var(--c-ink);
  color: #fff;
  font-weight: 600;
  text-decoration: none;
  transition: top var(--t-fast) var(--ease);
}
.skip-link:focus {
  top: 12px;
  color: #fff;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: var(--z-header);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(160%) blur(12px);
  border-bottom: 1px solid var(--c-border);
}
.topbar__inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: var(--sp-4);
  min-height: var(--header-h);
}

/* Navigation: second row on phones (scrolls sideways), inline from 900px. */
.nav {
  order: 3;
  flex: 1 1 100%;
  display: flex;
  gap: var(--sp-1);
  margin-inline: calc(var(--gutter) * -1);
  padding-inline: var(--gutter);
  overflow-x: auto;
  scrollbar-width: none;
}
.nav::-webkit-scrollbar {
  display: none;
}
.nav__link {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: none;
  padding: 10px;
  color: var(--c-text-muted);
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
  border-radius: var(--r-md);
  transition: color var(--t-fast) var(--ease);
}
.nav__link::after {
  content: '';
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 2px;
  border-radius: 2px;
  background: var(--c-primary);
  transform: scaleX(0);
  transition: transform var(--t-base) var(--ease);
}
.nav__link:hover {
  color: var(--c-ink);
}
.nav__link.is-active {
  color: var(--c-ink);
  font-weight: 600;
}
.nav__link.is-active::after {
  transform: scaleX(1);
}
.nav__link:focus-visible {
  outline-offset: -2px;
}
.nav__badge {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--r-pill);
  background: var(--c-primary);
  color: #fff;
  font-size: 0.6875rem;
  font-weight: 700;
}

.user {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-left: auto;
  min-width: 0;
}
.user__avatar {
  flex: none;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: var(--fs-xs);
  font-weight: 700;
}
.user__text {
  display: none;
  flex-direction: column;
  min-width: 0;
  max-width: 180px;
  line-height: 1.25;
}
.user__name {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-ink);
}
.user__role {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.user__logout-text {
  display: none;
}

/* The header row itself: logo left, user right; nav wraps below. */
.topbar__inner > :first-child {
  order: 1;
}
.user {
  order: 2;
}

@media (min-width: 640px) {
  .user__text {
    display: flex;
  }
  .user__logout-text {
    display: inline;
  }
}

@media (min-width: 900px) {
  .nav {
    order: 2;
    flex: 1 1 auto;
    margin-inline: var(--sp-4) 0;
    padding-inline: 0;
    overflow: visible;
  }
  .nav__link {
    padding: 22px 12px;
    border-radius: 0;
    font-size: 0.9375rem;
  }
  .nav__link::after {
    left: 12px;
    right: 12px;
  }
  .user {
    order: 3;
    margin-left: 0;
  }
}

.foot {
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
}
.foot__inner {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--sp-2) var(--sp-5);
  padding-block: var(--sp-5);
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
</style>
