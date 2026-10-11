<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'

// inverse / outline-inverse are for dark and brand-coloured backgrounds.
export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'inverse' | 'outline-inverse'
export type ButtonSize = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant
    size?: ButtonSize
    type?: 'button' | 'submit' | 'reset'
    /** Shows a spinner and blocks clicks. */
    loading?: boolean
    disabled?: boolean
    /** Full width. */
    block?: boolean
    /** Render as a router link instead of a <button>. */
    to?: RouteLocationRaw
  }>(),
  { variant: 'primary', size: 'md', type: 'button', loading: false, disabled: false, block: false, to: undefined },
)

const classes = computed(() => [
  'btn',
  `btn--${props.variant}`,
  `btn--${props.size}`,
  { 'btn--block': props.block, 'btn--loading': props.loading },
])
</script>

<template>
  <RouterLink v-if="to !== undefined && !disabled" :to="to" :class="classes">
    <slot />
  </RouterLink>
  <button v-else :class="classes" :type="type" :disabled="disabled || loading" :aria-busy="loading || undefined">
    <span v-if="loading" class="btn__spinner" aria-hidden="true"></span>
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  font-family: var(--font-sans);
  font-weight: 600;
  line-height: 1.2;
  text-decoration: none;
  white-space: nowrap;
  user-select: none;
  cursor: pointer;
  transition:
    background var(--t-fast) var(--ease),
    border-color var(--t-fast) var(--ease),
    color var(--t-fast) var(--ease),
    box-shadow var(--t-fast) var(--ease),
    transform var(--t-fast) var(--ease);
}
.btn:active:not(:disabled) {
  transform: translateY(1px);
}
.btn:disabled:not(.btn--loading) {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn--loading {
  opacity: 0.85;
  cursor: progress;
}

/* Sizes */
.btn--sm {
  min-height: 34px;
  padding: 6px 12px;
  font-size: var(--fs-sm);
}
.btn--md {
  min-height: 44px;
  padding: 10px 18px;
  font-size: 0.9375rem;
}
.btn--lg {
  min-height: 52px;
  padding: 14px 26px;
  font-size: var(--fs-base);
  border-radius: 12px;
}
.btn--block {
  display: flex;
  width: 100%;
}

/* Variants */
.btn--primary {
  background: var(--c-primary);
  color: var(--c-on-primary);
  box-shadow: 0 1px 2px rgba(64, 47, 255, 0.3);
}
.btn--primary:hover:not(:disabled) {
  background: var(--c-primary-hover);
  color: var(--c-on-primary);
}
.btn--primary:active:not(:disabled) {
  background: var(--c-primary-active);
}

.btn--secondary {
  background: var(--c-surface);
  color: var(--c-ink);
  border-color: var(--c-border-strong);
}
.btn--secondary:hover:not(:disabled) {
  border-color: var(--c-primary);
  color: var(--c-primary);
  background: var(--c-primary-soft);
}

.btn--ghost {
  background: transparent;
  color: var(--c-text-muted);
}
.btn--ghost:hover:not(:disabled) {
  background: rgba(27, 28, 33, 0.06);
  color: var(--c-ink);
}

.btn--danger {
  background: var(--c-surface);
  color: var(--c-danger-text);
  border-color: var(--c-danger-border);
}
.btn--danger:hover:not(:disabled) {
  background: var(--c-danger-soft);
  border-color: var(--c-danger);
  color: var(--c-danger-text);
}

.btn--inverse {
  background: #fff;
  color: var(--c-ink);
}
.btn--inverse:hover:not(:disabled) {
  background: var(--c-primary-soft);
  color: var(--c-ink);
}

.btn--outline-inverse {
  background: transparent;
  color: #fff;
  border-color: rgba(255, 255, 255, 0.45);
}
.btn--outline-inverse:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
  border-color: #fff;
  color: #fff;
}

/* Focus ring that works on dark backgrounds too */
.btn:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
  border-radius: var(--r-md);
}
.btn--inverse:focus-visible,
.btn--outline-inverse:focus-visible {
  outline-color: #fff;
}

.btn__spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid currentColor;
  border-right-color: transparent;
  animation: spin 0.7s linear infinite;
}
</style>
