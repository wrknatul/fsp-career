<script setup lang="ts">
import { RouterLink } from 'vue-router'

// Text logo. `inverse` for dark backgrounds. Links to the landing page.
withDefaults(defineProps<{ inverse?: boolean; to?: string }>(), { inverse: false, to: '/' })
</script>

<template>
  <RouterLink :to="to" class="logo" :class="{ 'logo--inverse': inverse }" aria-label="ФСП.Карьера — на главную">
    <span class="logo__mark" aria-hidden="true"></span>
    <span class="logo__text">ФСП<span class="logo__dot">.</span>Карьера</span>
  </RouterLink>
</template>

<style scoped>
.logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--c-ink);
  text-decoration: none;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.0625rem;
  letter-spacing: -0.03em;
  line-height: 1;
  border-radius: var(--r-sm);
}
.logo:hover {
  color: var(--c-ink);
}
.logo--inverse,
.logo--inverse:hover {
  color: #fff;
}
.logo__mark {
  position: relative;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--c-primary);
  flex: none;
}
/* Stylised "route": two nodes and a link between them. */
.logo__mark::before,
.logo__mark::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
}
.logo__mark::before {
  left: 4px;
  bottom: 4px;
}
.logo__mark::after {
  right: 4px;
  top: 4px;
}
.logo__dot {
  color: var(--c-primary);
}
.logo--inverse .logo__dot {
  color: #8f86ff;
}
</style>
