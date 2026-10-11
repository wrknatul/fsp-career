<script setup lang="ts">
import AppButton from './AppButton.vue'
import AppIcon from './AppIcon.vue'

export type BlockState = 'loading' | 'empty' | 'error'

// One block for the three non-content states of every page:
//   loading - skeleton with a short caption
//   empty   - title, text and an optional action in the "action" slot
//   error   - the server message (pass it as `text`) and a "Повторить" button
// Use it instead of the content while status !== 'ready'.
withDefaults(
  defineProps<{
    state: BlockState
    title?: string
    text?: string
    /** Caption of the retry button (error state). */
    retryLabel?: string
    /** Less padding, no border: for use inside cards. */
    compact?: boolean
  }>(),
  { retryLabel: 'Повторить', compact: false },
)

const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="state" :class="[`state--${state}`, { 'state--compact': compact }]">
    <template v-if="state === 'loading'">
      <div class="state__skeleton" role="status" aria-live="polite">
        <span class="sr-only">Загружаем…</span>
        <span class="skeleton skeleton--title"></span>
        <span class="skeleton"></span>
        <span class="skeleton skeleton--short"></span>
      </div>
      <p class="state__caption">{{ title ?? 'Загружаем…' }}</p>
    </template>

    <template v-else-if="state === 'error'">
      <span class="state__icon state__icon--error"><AppIcon name="alert" :size="22" /></span>
      <h3 class="state__title">{{ title ?? 'Не получилось загрузить' }}</h3>
      <p class="state__text" role="alert">{{ text ?? 'Что-то пошло не так. Попробуйте ещё раз.' }}</p>
      <AppButton variant="secondary" size="sm" @click="emit('retry')">{{ retryLabel }}</AppButton>
    </template>

    <template v-else>
      <span class="state__icon"><AppIcon name="spark" :size="22" /></span>
      <h3 class="state__title">{{ title ?? 'Здесь пока пусто' }}</h3>
      <p v-if="text" class="state__text">{{ text }}</p>
      <div v-if="$slots.action" class="state__action"><slot name="action" /></div>
    </template>
  </div>
</template>

<style scoped>
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-12) var(--sp-5);
  text-align: center;
  background: var(--c-surface);
  border: 1px dashed var(--c-border-strong);
  border-radius: var(--r-lg);
}
.state--loading {
  border-style: solid;
  border-color: var(--c-border);
}
.state--compact {
  padding: var(--sp-6) var(--sp-4);
  border: 0;
  background: transparent;
}
.state__icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--c-primary-soft);
  color: var(--c-primary);
}
.state__icon--error {
  background: var(--c-danger-soft);
  color: var(--c-danger-text);
}
.state__title {
  font-size: var(--fs-lg);
}
.state__text {
  max-width: 46ch;
  color: var(--c-text-muted);
  line-height: 1.55;
}
.state__action {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--sp-3);
  margin-top: var(--sp-2);
}
.state__caption {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.state__skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(100%, 360px);
}
.skeleton {
  display: block;
  height: 12px;
  border-radius: var(--r-pill);
  background: linear-gradient(90deg, #ededf0 25%, #f7f7f9 50%, #ededf0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}
.skeleton--title {
  height: 18px;
  width: 55%;
  margin-inline: auto;
}
.skeleton--short {
  width: 70%;
  margin-inline: auto;
}
</style>
