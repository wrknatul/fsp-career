<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    title: string
    size?: 'sm' | 'md' | 'lg'
    /** false: no close button, no Esc, no backdrop click (use while a request is in flight). */
    closable?: boolean
  }>(),
  { size: 'md', closable: true },
)

const open = defineModel<boolean>({ default: false })
const emit = defineEmits<{ close: [] }>()

const titleId = useId()
const dialogRef = ref<HTMLElement | null>(null)
let previouslyFocused: HTMLElement | null = null
let previousOverflow = ''

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function close(): void {
  if (!props.closable) {
    return
  }
  open.value = false
  emit('close')
}

function focusables(): HTMLElement[] {
  const root = dialogRef.value
  if (root === null) {
    return []
  }
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE))
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.stopPropagation()
    close()
    return
  }
  if (event.key !== 'Tab') {
    return
  }
  const items = focusables()
  if (items.length === 0) {
    event.preventDefault()
    dialogRef.value?.focus()
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || active === dialogRef.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

function lockScroll(): void {
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
}

function unlockScroll(): void {
  document.body.style.overflow = previousOverflow
}

watch(
  open,
  async (isOpen) => {
    if (isOpen) {
      previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
      lockScroll()
      await nextTick()
      const items = focusables()
      // Skip the close button so the first real control gets focus.
      const target = items.find((item) => !item.classList.contains('modal__close')) ?? items[0]
      ;(target ?? dialogRef.value)?.focus()
    } else {
      unlockScroll()
      previouslyFocused?.focus()
      previouslyFocused = null
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (open.value) {
    unlockScroll()
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="modal" @mousedown.self="close">
        <div
          ref="dialogRef"
          class="modal__dialog"
          :class="`modal__dialog--${size}`"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          tabindex="-1"
          @keydown="onKeydown"
        >
          <header class="modal__header">
            <h2 :id="titleId" class="modal__title">{{ title }}</h2>
            <button v-if="closable" type="button" class="modal__close" aria-label="Закрыть" @click="close">
              <AppIcon name="x" :size="20" />
            </button>
          </header>
          <div class="modal__body"><slot /></div>
          <footer v-if="$slots.footer" class="modal__footer"><slot name="footer" /></footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0;
  background: rgba(27, 28, 33, 0.56);
  backdrop-filter: blur(2px);
}
.modal__dialog {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: calc(100dvh - 24px);
  background: var(--c-surface);
  border-radius: var(--r-xl) var(--r-xl) 0 0;
  box-shadow: var(--shadow-lg);
  outline: none;
}
.modal__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
  padding: var(--sp-5) var(--sp-5) var(--sp-2);
}
.modal__title {
  font-size: var(--fs-lg);
}
.modal__close {
  flex: none;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  margin: -6px -8px 0 0;
  border: 0;
  border-radius: var(--r-md);
  background: transparent;
  color: var(--c-text-muted);
  transition: background var(--t-fast) var(--ease);
}
.modal__close:hover {
  background: var(--c-neutral-soft);
  color: var(--c-ink);
}
.modal__body {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-2) var(--sp-5) var(--sp-5);
  overflow-y: auto;
  color: var(--c-text-muted);
}
.modal__footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--sp-3);
  padding: var(--sp-4) var(--sp-5) var(--sp-5);
  border-top: 1px solid var(--c-border);
}

@media (min-width: 640px) {
  .modal {
    align-items: center;
    padding: var(--sp-6);
  }
  .modal__dialog {
    border-radius: var(--r-xl);
    max-height: calc(100dvh - 48px);
  }
  .modal__dialog--sm {
    max-width: 420px;
  }
  .modal__dialog--md {
    max-width: 560px;
  }
  .modal__dialog--lg {
    max-width: 760px;
  }
  .modal__header {
    padding: var(--sp-6) var(--sp-6) var(--sp-2);
  }
  .modal__body {
    padding: var(--sp-2) var(--sp-6) var(--sp-6);
  }
  .modal__footer {
    padding: var(--sp-4) var(--sp-6) var(--sp-6);
  }
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--t-base) var(--ease);
}
.modal-enter-active .modal__dialog,
.modal-leave-active .modal__dialog {
  transition: transform var(--t-base) var(--ease);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .modal__dialog,
.modal-leave-to .modal__dialog {
  transform: translateY(16px);
}
</style>
