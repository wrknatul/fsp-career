<script setup lang="ts">
// Centered card for login / register. Slots: default (form), "footer" (link to the other form).
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <div class="auth">
    <div class="container auth__inner">
      <div class="auth__card card card--lg">
        <header class="auth__head">
          <h1 class="auth__title">{{ title }}</h1>
          <p v-if="subtitle" class="auth__subtitle">{{ subtitle }}</p>
        </header>
        <slot />
        <footer v-if="$slots.footer" class="auth__footer"><slot name="footer" /></footer>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth {
  padding-block: var(--sp-8) var(--sp-16);
  background:
    radial-gradient(60% 40% at 50% 0%, rgba(64, 47, 255, 0.08), transparent 70%),
    var(--c-bg);
}
.auth__inner {
  display: flex;
  justify-content: center;
}
.auth__card {
  width: 100%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}
.auth__head {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.auth__title {
  font-size: var(--fs-2xl);
  letter-spacing: -0.03em;
}
.auth__subtitle {
  color: var(--c-text-muted);
  line-height: 1.55;
}
.auth__footer {
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
  text-align: center;
}
@media (min-width: 768px) {
  .auth {
    padding-block: var(--sp-16) var(--sp-20);
  }
}
</style>
