<script setup lang="ts">
import { computed } from 'vue'

import type { Category } from '@/api/types'
import AppIcon from '@/components/AppIcon.vue'
import { formatPoints, formatScore } from '@/utils/format'

// "Было → стало" after an action that changes the profile (link FSP, parse resume, pass a test).
const props = withDefaults(defineProps<{ before: Category; after: Category; title?: string }>(), {
  title: 'Что изменилось в категории',
})

const labelChanged = computed(() => props.before.label !== props.after.label)
const pointsDelta = computed(() => Math.round((props.after.grade_points - props.before.grade_points) * 10) / 10)
const indexDelta = computed(() => Math.round(props.after.confidence_index - props.before.confidence_index))
const changed = computed(() => labelChanged.value || pointsDelta.value !== 0 || indexDelta.value !== 0)

function tone(delta: number): string {
  if (delta > 0) return 'is-up'
  if (delta < 0) return 'is-down'
  return ''
}
</script>

<template>
  <section class="chg card card--flat" :aria-label="title">
    <p class="eyebrow">{{ title }}</p>

    <div class="chg__pair">
      <div class="chg__side">
        <p class="chg__cap">Было</p>
        <p class="chg__label">{{ before.label }}</p>
      </div>
      <span class="chg__arrow" aria-hidden="true"><AppIcon name="arrow-right" :size="20" /></span>
      <div class="chg__side chg__side--after">
        <p class="chg__cap">Стало</p>
        <p class="chg__label">{{ after.label }}</p>
      </div>
    </div>

    <dl class="chg__nums">
      <div class="chg__num">
        <dt>Баллы грейда</dt>
        <dd class="num">
          {{ formatScore(before.grade_points) }} → {{ formatScore(after.grade_points) }}
          <span v-if="pointsDelta !== 0" class="chg__delta" :class="tone(pointsDelta)">{{ formatPoints(pointsDelta) }}</span>
        </dd>
      </div>
      <div class="chg__num">
        <dt>Индекс подтверждённости</dt>
        <dd class="num">
          {{ Math.round(before.confidence_index) }} → {{ Math.round(after.confidence_index) }}
          <span v-if="indexDelta !== 0" class="chg__delta" :class="tone(indexDelta)">
            {{ indexDelta > 0 ? '+' : '−' }}{{ Math.abs(indexDelta) }}
          </span>
        </dd>
      </div>
    </dl>

    <p v-if="!changed" class="chg__same">Категория и баллы остались прежними.</p>
    <p v-if="after.grade_note" class="chg__note">
      <AppIcon name="info" :size="16" />
      <span>{{ after.grade_note }}</span>
    </p>
  </section>
</template>

<style scoped>
.chg {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  background: var(--c-surface-2);
}
.chg__pair {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-2);
  align-items: center;
}
.chg__side {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: var(--sp-3) var(--sp-4);
  border: 1px dashed var(--c-border-strong);
  border-radius: var(--r-md);
}
.chg__side--after {
  border: 1px solid var(--c-primary);
  background: var(--c-primary-soft);
}
.chg__cap {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.chg__label {
  font-family: var(--font-mono);
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.3;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.chg__arrow {
  display: grid;
  place-items: center;
  color: var(--c-primary);
  transform: rotate(90deg);
}
.chg__nums {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: var(--sp-3) var(--sp-5);
  margin: 0;
}
.chg__num {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.chg__num dt {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.chg__num dd {
  margin: 0;
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--c-ink);
}
.chg__delta {
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 700;
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
}
.chg__delta.is-up {
  background: var(--c-success-soft);
  color: var(--c-success-text);
}
.chg__delta.is-down {
  background: var(--c-danger-soft);
  color: var(--c-danger-text);
}
.chg__same {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.chg__note {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-ink);
}
.chg__note :deep(svg) {
  margin-top: 2px;
  color: var(--c-primary);
}

@media (min-width: 720px) {
  .chg__pair {
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    gap: var(--sp-3);
  }
  .chg__arrow {
    transform: none;
  }
}
</style>
