<script setup lang="ts">
// Number tile: "42 · Всего кандидатов". Value is set in the mono font.
withDefaults(
  defineProps<{
    label: string
    value: string | number
    hint?: string
    tone?: 'default' | 'primary' | 'success' | 'warning'
  }>(),
  { tone: 'default' },
)
</script>

<template>
  <div class="tile" :class="`tile--${tone}`">
    <p class="tile__label">{{ label }}</p>
    <p class="tile__value num">{{ value }}</p>
    <p v-if="hint" class="tile__hint">{{ hint }}</p>
    <slot />
  </div>
</template>

<style scoped>
.tile {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--sp-4) var(--sp-5);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-sm);
  min-width: 0;
}
.tile__label {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--c-text-muted);
}
.tile__value {
  font-size: clamp(1.75rem, 1.4rem + 1.2vw, 2.25rem);
  font-weight: 600;
  line-height: 1.1;
  color: var(--c-ink);
}
.tile__hint {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.tile--primary .tile__value {
  color: var(--c-primary);
}
.tile--success .tile__value {
  color: var(--c-success-text);
}
.tile--warning .tile__value {
  color: var(--c-warning-text);
}
</style>
