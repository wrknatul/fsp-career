<script setup lang="ts">
import { computed } from 'vue'

import type { Category } from '@/api/types'

import AppIcon from './AppIcon.vue'

// Confirmation index 0..100 with the breakdown ("what gives points and what is still missing").
//   <ConfidenceMeter :category="profile.category" />
const props = withDefaults(
  defineProps<{
    category: Pick<Category, 'confidence_index' | 'confidence_breakdown'>
    title?: string
  }>(),
  { title: 'Индекс подтверждённости' },
)

const index = computed(() => Math.min(100, Math.max(0, Math.round(props.category.confidence_index))))
const verdict = computed(() => {
  if (index.value >= 75) return 'Профиль хорошо подтверждён'
  if (index.value >= 50) return 'Есть опора на подтверждения'
  if (index.value > 0) return 'Подтверждений пока мало'
  return 'Пока ничего не подтверждено'
})
</script>

<template>
  <section class="meter card" :aria-label="title">
    <header class="meter__head">
      <div>
        <p class="eyebrow">{{ title }}</p>
        <p class="meter__verdict">{{ verdict }}</p>
      </div>
      <p class="meter__value num"><span>{{ index }}</span><small>/100</small></p>
    </header>

    <div
      class="meter__track"
      role="progressbar"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-valuenow="index"
      :aria-label="title"
    >
      <span class="meter__fill" :style="{ width: `${index}%` }"></span>
    </div>

    <ul class="meter__list">
      <li v-for="item in category.confidence_breakdown" :key="item.label" class="meter__item" :class="{ 'is-done': item.done }">
        <span class="meter__mark" aria-hidden="true"><AppIcon v-if="item.done" name="check" :size="12" /></span>
        <span class="meter__label">{{ item.label }}</span>
        <span class="meter__points num">{{ item.points }}<span class="meter__max">/{{ item.max }}</span></span>
        <span class="sr-only">{{ item.done ? 'выполнено' : 'не выполнено' }}</span>
      </li>
    </ul>
    <p class="meter__foot">В индекс входят только результаты ФСП и сданные тесты. Резюме и анкета — это не подтверждение.</p>
  </section>
</template>

<style scoped>
.meter {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.meter__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--sp-4);
}
.meter__verdict {
  margin-top: 4px;
  font-weight: 600;
  color: var(--c-ink);
}
.meter__value {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-size: clamp(2rem, 1.5rem + 2vw, 2.75rem);
  font-weight: 700;
  line-height: 1;
  color: var(--c-primary);
}
.meter__value small {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--c-text-muted);
}
.meter__track {
  height: 10px;
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  overflow: hidden;
}
.meter__fill {
  display: block;
  height: 100%;
  border-radius: var(--r-pill);
  background: var(--c-primary);
  transition: width 700ms var(--ease);
}
.meter__list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.meter__item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.meter__item.is-done {
  color: var(--c-text);
}
.meter__mark {
  flex: none;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1.5px solid var(--c-border-strong);
  color: #fff;
}
.meter__item.is-done .meter__mark {
  border-color: var(--c-success);
  background: var(--c-success);
}
.meter__label {
  flex: 1;
  min-width: 0;
}
.meter__points {
  font-weight: 600;
  color: var(--c-ink);
}
.meter__max {
  font-weight: 400;
  color: var(--c-text-muted);
}
.meter__foot {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  line-height: 1.5;
}
</style>
