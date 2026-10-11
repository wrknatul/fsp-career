<script setup lang="ts">
import { computed, useId } from 'vue'

import type { Category } from '@/api/types'
import { formatPoints, formatScore } from '@/utils/format'

import AppIcon from './AppIcon.vue'
import SourceBadge from './SourceBadge.vue'

// Expandable "why this grade": every contribution with a bar, ceilings (negative rows) highlighted,
// the total equals category.grade_points, plus a scale with the grade thresholds.
//   <GradeExplanation :category="profile.category" />           collapsed
//   <GradeExplanation :category="profile.category" open />      expanded initially
//   <GradeExplanation v-model:open="shown" ... />               controlled
const props = withDefaults(defineProps<{ category: Category; title?: string }>(), {
  title: 'Почему этот грейд',
})

const open = defineModel<boolean>('open', { default: false })

const panelId = useId()

// Grade thresholds from the spec: < 6 intern, 6-35 junior, 35-70 middle, >= 70 senior.
const SCALE_MAX = 100
const SEGMENTS = [
  { id: 'intern', title: 'Стажёр', from: 0, to: 6 },
  { id: 'junior', title: 'Junior', from: 6, to: 35 },
  { id: 'middle', title: 'Middle', from: 35, to: 70 },
  { id: 'senior', title: 'Senior', from: 70, to: SCALE_MAX },
] as const

// The backend labels a ceiling row "Потолок: не больше N баллов за …". The row already carries a "потолок" pill,
// so the prefix is dropped to avoid saying it twice.
const CAP_PREFIX = /^Потолок:\s*/i

function rowLabel(label: string, negative: boolean): string {
  if (!negative) {
    return label
  }
  const stripped = label.replace(CAP_PREFIX, '')
  return stripped === '' ? label : stripped
}

const rows = computed(() => {
  const maxAbs = Math.max(1, ...props.category.grade_explanations.map((row) => Math.abs(row.points)))
  return props.category.grade_explanations.map((row, index) => {
    const negative = row.points < 0
    return {
      key: `${index}-${row.label}`,
      ...row,
      label: rowLabel(row.label, negative),
      negative,
      width: `${Math.max(3, (Math.abs(row.points) / maxAbs) * 100)}%`,
    }
  })
})

const markerLeft = computed(() => `${Math.min(SCALE_MAX, Math.max(0, props.category.grade_points))}%`)
const hasRows = computed(() => rows.value.length > 0)
</script>

<template>
  <section class="why card card--flat">
    <button
      type="button"
      class="why__toggle"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="open = !open"
    >
      <span class="why__toggle-title">{{ title }}</span>
      <span class="why__toggle-total num">{{ formatScore(category.grade_points) }} баллов</span>
      <span class="why__chevron" :class="{ 'is-open': open }"><AppIcon name="chevron-down" :size="18" /></span>
    </button>

    <Transition name="slide-down">
      <div v-show="open" :id="panelId" class="why__panel">
        <p v-if="!hasRows" class="why__empty">
          Пока нечего считать: нет ни опыта, ни результатов, ни тестов. Как только появится первый подтверждённый
          факт, здесь будет видно, из чего складывается грейд.
        </p>

        <ul v-else class="why__rows">
          <li v-for="row in rows" :key="row.key" class="why__row" :class="{ 'is-negative': row.negative }">
            <div class="why__row-head">
              <span class="why__label">
                <span v-if="row.negative" class="why__cap">потолок</span>
                {{ row.label }}
              </span>
              <SourceBadge v-if="row.verification" :verification="row.verification" size="sm" />
              <span class="why__points num">{{ formatPoints(row.points) }}</span>
            </div>
            <div class="why__bar" aria-hidden="true"><span class="why__bar-fill" :style="{ width: row.width }"></span></div>
          </li>
          <li class="why__row why__row--total">
            <div class="why__row-head">
              <span class="why__label">Итого</span>
              <span class="why__points num">{{ formatScore(category.grade_points) }}</span>
            </div>
          </li>
        </ul>

        <div class="why__scale" aria-label="Шкала грейдов">
          <div class="why__track">
            <span
              v-for="segment in SEGMENTS"
              :key="segment.id"
              class="why__segment"
              :class="{ 'is-current': segment.id === category.grade }"
              :style="{ width: `${((segment.to - segment.from) / SCALE_MAX) * 100}%` }"
            ></span>
            <span class="why__marker" :style="{ left: markerLeft }"></span>
          </div>
          <div class="why__ticks num" aria-hidden="true">
            <span v-for="segment in SEGMENTS" :key="segment.id" :style="{ left: `${(segment.from / SCALE_MAX) * 100}%` }">
              {{ segment.from }}
            </span>
          </div>
          <p class="why__legend">
            Стажёр до 6 · Junior 6–35 · Middle 35–70 · Senior от 70. Баллы за разряды ФСП условные и уточняются с
            Федерацией.
          </p>
        </div>
      </div>
    </Transition>
  </section>
</template>

<style scoped>
.why {
  padding: 0;
  overflow: hidden;
}
.why__toggle {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  width: 100%;
  padding: var(--sp-4) var(--sp-5);
  border: 0;
  background: transparent;
  text-align: left;
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: var(--fs-base);
  color: var(--c-ink);
  transition: background var(--t-fast) var(--ease);
}
.why__toggle:hover {
  background: var(--c-surface-2);
}
.why__toggle:focus-visible {
  outline-offset: -3px;
}
.why__toggle-title {
  flex: 1;
  letter-spacing: -0.02em;
}
.why__toggle-total {
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--c-text-muted);
}
.why__chevron {
  display: grid;
  color: var(--c-text-muted);
  transition: transform var(--t-base) var(--ease);
}
.why__chevron.is-open {
  transform: rotate(180deg);
}
.why__panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  padding: var(--sp-2) var(--sp-5) var(--sp-5);
  border-top: 1px solid var(--c-border);
  padding-top: var(--sp-4);
}
.why__empty {
  color: var(--c-text-muted);
  line-height: 1.55;
}
.why__rows {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.why__row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.why__row-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.why__label {
  flex: 1;
  min-width: 0;
  font-size: var(--fs-sm);
  line-height: 1.4;
  color: var(--c-text);
}
.why__points {
  flex: none;
  min-width: 56px;
  text-align: right;
  font-weight: 600;
  font-size: var(--fs-base);
}
.why__bar {
  height: 6px;
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  overflow: hidden;
}
.why__bar-fill {
  display: block;
  height: 100%;
  border-radius: var(--r-pill);
  background: var(--c-primary);
}
.why__row.is-negative .why__label,
.why__row.is-negative .why__points {
  color: var(--c-danger-text);
}
.why__row.is-negative .why__bar-fill {
  background: repeating-linear-gradient(135deg, var(--c-danger) 0 4px, #ff8a8c 4px 8px);
}
.why__cap {
  display: inline-block;
  margin-right: 6px;
  padding: 0 7px;
  border-radius: var(--r-pill);
  background: var(--c-danger-soft);
  border: 1px solid var(--c-danger-border);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-danger-text);
}
.why__row--total {
  padding-top: var(--sp-3);
  border-top: 1px solid var(--c-border);
}
.why__row--total .why__label {
  font-family: var(--font-mono);
  font-weight: 700;
}
.why__row--total .why__points {
  font-size: var(--fs-lg);
  color: var(--c-primary);
}
.why__scale {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.why__track {
  position: relative;
  display: flex;
  height: 10px;
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  overflow: visible;
}
.why__segment {
  height: 100%;
  background: var(--c-neutral-soft);
  border-right: 2px solid var(--c-surface);
}
.why__segment:first-child {
  border-radius: var(--r-pill) 0 0 var(--r-pill);
}
.why__segment:nth-child(4) {
  border-right: 0;
  border-radius: 0 var(--r-pill) var(--r-pill) 0;
}
.why__segment.is-current {
  background: var(--c-primary-soft-2);
}
.why__marker {
  position: absolute;
  top: -5px;
  width: 4px;
  height: 20px;
  margin-left: -2px;
  border-radius: 2px;
  background: var(--c-primary);
  box-shadow: 0 0 0 2px var(--c-surface);
}
.why__ticks {
  position: relative;
  height: 16px;
  font-size: 0.6875rem;
  color: var(--c-text-muted);
}
.why__ticks span {
  position: absolute;
  top: 0;
  transform: translateX(-1px);
}
.why__legend {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  line-height: 1.5;
}
</style>
