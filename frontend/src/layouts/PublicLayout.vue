<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import AppLogo from '@/components/AppLogo.vue'
import DemoBanner from '@/components/DemoBanner.vue'
import { useAuthStore } from '@/stores/auth'

// Layout of the public pages: landing, login, register, privacy, 404.
// Full-bleed: every page puts its own .container inside.
const auth = useAuthStore()

function focusMain(): void {
  document.getElementById('main')?.focus()
}
</script>

<template>
  <div class="shell">
    <a href="#main" class="skip-link" @click.prevent="focusMain">К содержимому</a>
    <DemoBanner />

    <header class="topbar">
      <div class="container topbar__inner">
        <AppLogo />
        <nav class="topbar__nav" aria-label="Основная навигация">
          <RouterLink :to="{ name: 'landing', hash: '#how' }" class="topbar__link">Как это работает</RouterLink>
          <RouterLink :to="{ name: 'privacy' }" class="topbar__link">Приватность</RouterLink>
        </nav>
        <div class="topbar__actions">
          <AppButton v-if="auth.isAuthenticated" :to="auth.homePath" size="sm">В кабинет</AppButton>
          <template v-else>
            <AppButton :to="{ name: 'login' }" variant="ghost" size="sm">Войти</AppButton>
            <AppButton :to="{ name: 'register' }" size="sm">Регистрация</AppButton>
          </template>
        </div>
      </div>
    </header>

    <main id="main" class="shell__main" tabindex="-1">
      <RouterView v-slot="{ Component, route }">
        <component :is="Component" :key="route.path" />
      </RouterView>
    </main>

    <footer class="footer">
      <div class="container footer__inner">
        <div class="footer__brand">
          <AppLogo inverse />
          <p class="footer__text">
            Прототип для хакатона «Лидеры цифровой трансформации» 2026, спецтрек Федерации спортивного
            программирования. Команда «Граф магистралей».
          </p>
        </div>
        <ul class="footer__links">
          <li><RouterLink :to="{ name: 'privacy' }">Приватность и данные</RouterLink></li>
          <li><RouterLink :to="{ name: 'landing', hash: '#how' }">Как это работает</RouterLink></li>
        </ul>
        <p class="footer__note">Все данные реестра ФСП в демо вымышлены.</p>
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
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: saturate(160%) blur(12px);
  border-bottom: 1px solid var(--c-border);
}
.topbar__inner {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  min-height: var(--header-h);
}
.topbar__nav {
  display: none;
  margin-left: var(--sp-6);
  gap: var(--sp-1);
}
.topbar__link {
  padding: 8px 12px;
  border-radius: var(--r-md);
  color: var(--c-text-muted);
  font-size: 0.9375rem;
  font-weight: 500;
  text-decoration: none;
  transition:
    background var(--t-fast) var(--ease),
    color var(--t-fast) var(--ease);
}
.topbar__link:hover {
  background: rgba(27, 28, 33, 0.06);
  color: var(--c-ink);
}
.topbar__actions {
  display: flex;
  gap: var(--sp-2);
  margin-left: auto;
}
@media (min-width: 720px) {
  .topbar__nav {
    display: flex;
  }
}

.footer {
  background: var(--c-ink);
  color: var(--c-on-ink-muted);
}
.footer__inner {
  display: grid;
  gap: var(--sp-6);
  padding-block: var(--sp-10);
}
.footer__brand {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  max-width: 52ch;
}
.footer__text,
.footer__note {
  font-size: var(--fs-sm);
  line-height: 1.55;
}
.footer__links {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2) var(--sp-5);
}
.footer__links a {
  color: var(--c-on-ink);
  font-size: var(--fs-sm);
  text-underline-offset: 3px;
}
.footer__links a:hover {
  color: #fff;
}
.footer a:focus-visible {
  outline-color: #fff;
}
@media (min-width: 900px) {
  .footer__inner {
    grid-template-columns: 1.4fr 1fr auto;
    align-items: start;
  }
  .footer__note {
    max-width: 28ch;
    text-align: right;
  }
}
</style>
