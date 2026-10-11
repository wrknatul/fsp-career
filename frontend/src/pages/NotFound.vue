<script setup lang="ts">
import AppButton from '@/components/AppButton.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <section class="nf">
    <div class="container nf__inner">
      <p class="nf__code num" aria-hidden="true">404</p>
      <h1 class="nf__title">Такой страницы нет</h1>
      <p class="nf__text">
        Возможно, ссылка устарела или в адресе опечатка. Вернитесь на главную или в свой кабинет — оттуда всё
        находится.
      </p>
      <div class="row">
        <AppButton :to="{ name: 'landing' }">На главную</AppButton>
        <AppButton v-if="auth.isAuthenticated" :to="auth.homePath" variant="secondary">В кабинет</AppButton>
      </div>
    </div>
  </section>
</template>

<style scoped>
.nf {
  padding-block: var(--sp-16) var(--sp-20);
}
.nf__inner {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-4);
}
.nf__code {
  font-size: clamp(5rem, 3rem + 10vw, 9rem);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.06em;
  color: var(--c-primary);
}
.nf__title {
  font-size: var(--fs-2xl);
}
.nf__text {
  max-width: 48ch;
  color: var(--c-text-muted);
  line-height: 1.6;
}
</style>
