<script setup lang="ts">
import { computed } from 'vue'

import type { MatchComponents } from '@/api/types'
import { formatPercent } from '@/utils/format'

// Four components of the match score (each 0..1). `null` means "not counted": the query had no skills or no text,
// the weights of the others were redistributed by the server.
//   <ScoreBreakdown :components="match.components" />
const props = defineProps<{ components: MatchComponents }>()

type Row = { key: string; label: string; hint: string; value: number | null }

const rows = computed<Row[]>(() => [
  {
    key: 'skill',
    label: 'Навыки',
    hint: 'Сколько нужных навыков есть у кандидата и насколько сильно они подтверждены',
    value: props.components.skill,
  },
  {
    key: 'text',
    label: 'Совпадение с текстом запроса',
    hint: 'Лексическое сходство текста запроса и профиля: общие слова и термины, а не смысл',
    value: props.components.text,
  },
  {
    key: 'track',
    label: 'Опыт и достижения',
    hint: 'Результаты ФСП, разряд и опыт работы',
    value: props.components.track_record,
  },
  {
    key: 'confidence',
    label: 'Подтверждённость',
    hint: 'Насколько профиль подтверждён ФСП и тестами платформы, а не только словами',
    value: props.components.confidence,
  },
])

function width(value: number | null): string {
  if (value === null) {
    return '0%'
  }
  return `${Math.min(100, Math.max(0, value * 100))}%`
}
</script>

<template>
  <ul class="breakdown" aria-label="Из чего складывается оценка">
    <li v-for="row in rows" :key="row.key" class="breakdown__row" :title="row.hint">
      <div class="breakdown__head">
        <span class="breakdown__label">{{ row.label }}</span>
        <span v-if="row.value !== null" class="breakdown__value num">{{ formatPercent(row.value) }}</span>
        <span v-else class="breakdown__skipped">не учитывалась</span>
      </div>
      <div class="breakdown__track" :class="{ 'is-skipped': row.value === null }" aria-hidden="true">
        <span class="breakdown__fill" :class="`breakdown__fill--${row.key}`" :style="{ width: width(row.value) }"></span>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.breakdown {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--sp-3) var(--sp-6);
  margin: 0;
  list-style: none;
}
@media (min-width: 560px) {
  .breakdown {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.breakdown__row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.breakdown__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-3);
}
.breakdown__label {
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-text);
  line-height: 1.3;
}
.breakdown__value {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-ink);
}
.breakdown__skipped {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  white-space: nowrap;
}
.breakdown__track {
  height: 6px;
  border-radius: var(--r-pill);
  background: var(--c-border);
  overflow: hidden;
}
.breakdown__track.is-skipped {
  background: repeating-linear-gradient(90deg, var(--c-border) 0 6px, transparent 6px 10px);
}
.breakdown__fill {
  display: block;
  height: 100%;
  border-radius: var(--r-pill);
  background: var(--c-primary);
  transition: width 500ms var(--ease);
}
.breakdown__fill--text {
  background: #7d72ff;
}
.breakdown__fill--track {
  background: var(--c-ink-3);
}
.breakdown__fill--confidence {
  background: var(--c-success);
}
</style>
