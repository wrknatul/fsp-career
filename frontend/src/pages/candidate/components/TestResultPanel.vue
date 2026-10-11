<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { Category, TestResult } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import { formatPercent } from '@/utils/format'

import CategoryChange from './CategoryChange.vue'

// Result of a finished test: level, correct answers and what changed in the grade.
defineProps<{ result: TestResult; before: Category | null; skillTitle: string }>()
const emit = defineEmits<{ back: [] }>()

// The "Submit" button is gone from the DOM: move focus to the level so keyboard and screen-reader users land on the result.
const levelRef = ref<HTMLElement | null>(null)
onMounted(() => {
  levelRef.value?.focus({ preventScroll: true })
})
</script>

<template>
  <section class="tr card card--lg" :class="{ 'is-pass': result.passed }" aria-live="polite">
    <p class="eyebrow">Результат · {{ skillTitle }}</p>

    <div class="tr__hero">
      <p class="tr__score">
        <span class="tr__big num">{{ result.correct }}</span>
        <span class="tr__of num">из {{ result.total }}</span>
        <span class="tr__cap">верных</span>
      </p>
      <div class="tr__level">
        <p ref="levelRef" class="tr__level-title" tabindex="-1">{{ result.level_title }}</p>
        <p v-if="result.passed" class="tr__verdict">
          <SourceBadge verification="tested" />
          <span>Навык «{{ skillTitle }}» теперь подтверждён тестом. Набрано <b class="num">{{ formatPercent(result.score) }}</b> от максимума.</span>
        </p>
        <p v-else class="tr__verdict">
          <span>
            Навык в профиль не добавлен: набрано <b class="num">{{ formatPercent(result.score) }}</b>, до базового уровня не хватило.
            Прежние результаты не изменились, а пересдать можно после паузы.
          </span>
        </p>
      </div>
    </div>

    <CategoryChange v-if="result.passed && before" :before="before" :after="result.profile.category" title="Что изменилось в грейде" />

    <p class="tr__note">Экспресс-проверка из 6 вопросов: ориентир, а не аттестация.</p>

    <div class="tr__actions">
      <AppButton @click="emit('back')">К списку тестов</AppButton>
      <AppButton to="/candidate" variant="secondary">На обзор профиля</AppButton>
    </div>
  </section>
</template>

<style scoped>
.tr {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  max-width: 760px;
  width: 100%;
  margin-inline: auto;
}
.tr.is-pass {
  border-color: var(--c-success-border);
}
.tr__hero {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-5) var(--sp-8);
}
.tr__score {
  display: flex;
  align-items: baseline;
  gap: 8px;
  color: var(--c-ink);
}
.tr__big {
  font-size: clamp(3rem, 2.4rem + 3vw, 4.5rem);
  font-weight: 700;
  line-height: 1;
  color: var(--c-ink);
}
.tr.is-pass .tr__big {
  color: var(--c-success-text);
}
.tr__of {
  font-size: var(--fs-xl);
  font-weight: 600;
}
.tr__cap {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.tr__level {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  flex: 1 1 260px;
  min-width: 0;
}
.tr__level-title {
  font-family: var(--font-mono);
  font-size: var(--fs-xl);
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--c-ink);
}
.tr__verdict {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-3);
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--c-text-muted);
}
.tr__note {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.tr__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}
</style>
