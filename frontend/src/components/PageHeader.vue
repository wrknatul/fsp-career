<script setup lang="ts">
// Page title block. Slot "actions" sits on the right (stacks below the title on phones).
defineProps<{
  title: string
  subtitle?: string
  /** Small uppercase line above the title, e.g. "Соискатель". */
  eyebrow?: string
}>()
</script>

<template>
  <header class="page-header">
    <div class="page-header__text">
      <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
      <h1 class="page-header__title">{{ title }}</h1>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
      <slot />
    </div>
    <div v-if="$slots.actions" class="page-header__actions"><slot name="actions" /></div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.page-header__text {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  min-width: 0;
}
.page-header__title {
  font-size: clamp(1.5rem, 1.2rem + 1.4vw, 2.125rem);
  letter-spacing: -0.03em;
}
.page-header__subtitle {
  max-width: 64ch;
  color: var(--c-text-muted);
  font-size: var(--fs-base);
  line-height: 1.55;
}
.page-header__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}

@media (min-width: 768px) {
  .page-header {
    flex-direction: row;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--sp-6);
  }
  .page-header__actions {
    flex: none;
    justify-content: flex-end;
  }
}
</style>
