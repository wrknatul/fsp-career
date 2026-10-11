<script setup lang="ts">
import { useToastStore } from '@/stores/toast'

import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

// Mounted once in App.vue. Push messages with useToastStore().
const store = useToastStore()

const ICONS = { success: 'check', error: 'alert', info: 'info' } as const satisfies Record<string, IconName>
</script>

<template>
  <div class="toasts" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="toast">
      <div
        v-for="toast in store.toasts"
        :key="toast.id"
        class="toast"
        :class="`toast--${toast.kind}`"
        :role="toast.kind === 'error' ? 'alert' : 'status'"
      >
        <span class="toast__icon"><AppIcon :name="ICONS[toast.kind]" :size="16" /></span>
        <p class="toast__text">{{ toast.message }}</p>
        <button type="button" class="toast__close" aria-label="Закрыть уведомление" @click="store.dismiss(toast.id)">
          <AppIcon name="x" :size="16" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toasts {
  position: fixed;
  z-index: var(--z-toast);
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 8px 12px 14px;
  border-radius: var(--r-md);
  background: var(--c-ink);
  color: var(--c-on-ink);
  box-shadow: var(--shadow-lg);
  font-size: var(--fs-sm);
  line-height: 1.45;
}
.toast__icon {
  flex: none;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
}
.toast--success .toast__icon {
  background: var(--c-success);
  color: #fff;
}
.toast--error .toast__icon {
  background: var(--c-danger);
  color: #fff;
}
.toast--info .toast__icon {
  background: var(--c-primary);
  color: #fff;
}
.toast__text {
  flex: 1;
  padding-top: 2px;
  min-width: 0;
  overflow-wrap: anywhere;
}
.toast__close {
  flex: none;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--c-on-ink-muted);
}
.toast__close:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}
.toast__close:focus-visible {
  outline-color: #fff;
}

@media (min-width: 640px) {
  .toasts {
    left: auto;
    right: 24px;
    bottom: 24px;
    width: 380px;
  }
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity var(--t-base) var(--ease),
    transform var(--t-base) var(--ease);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
