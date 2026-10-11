<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { CategoryMatrix, Grade, Stack } from '@/api/types'
import AppIcon from '@/components/AppIcon.vue'
import { searchLocation, type SearchFilters } from '@/pages/employer/searchFilters'
import { useReferenceStore } from '@/stores/reference'
import { formatCount } from '@/utils/format'
import { GRADE_ORDER, STACK_ORDER } from '@/utils/labels'

// Heat map "stack x grade": the darker the cell, the more candidates in the category.
// A cell shows the number of candidates and how many of them have FSP results; a click opens the search
// with exactly this category. `carry` holds the filters that stay on when going into the search.
//   <HeatMatrix :matrix="matrix" :carry="{ team_roles: ['developer'] }" />
const props = withDefaults(defineProps<{ matrix: CategoryMatrix; carry?: Partial<SearchFilters> }>(), {
  carry: () => ({}),
})

const reference = useReferenceStore()

type Cell = { count: number; fsp: number; style: Record<string, string>; hot: boolean; share: number }

const CANDIDATES = ['кандидат', 'кандидата', 'кандидатов'] as const

const cellByKey = computed(() => {
  const map = new Map<string, { count: number; fsp: number }>()
  for (const cell of props.matrix.cells) {
    map.set(`${cell.stack}:${cell.grade}`, { count: cell.count, fsp: cell.fsp_verified })
  }
  return map
})

const maxCount = computed(() => Math.max(1, ...props.matrix.cells.map((cell) => cell.count)))

const stackTotals = computed(() => new Map(props.matrix.by_stack.map((item) => [item.stack, item.count])))
const gradeTotals = computed(() => new Map(props.matrix.by_grade.map((item) => [item.grade, item.count])))

const stacksWithPeople = computed(() => {
  const present = new Set<Stack>(props.matrix.cells.map((cell) => cell.stack))
  return STACK_ORDER.filter((stack) => present.has(stack))
})
const emptyStacks = computed(() => STACK_ORDER.filter((stack) => !stacksWithPeople.value.includes(stack)))

function cellOf(stack: Stack, grade: Grade): Cell | null {
  const found = cellByKey.value.get(`${stack}:${grade}`)
  if (found === undefined || found.count === 0) {
    return null
  }
  // Square-root scale: a single candidate stays visible next to a crowded category.
  const heat = Math.sqrt(found.count / maxCount.value)
  const alpha = 0.1 + heat * 0.85
  return {
    count: found.count,
    fsp: found.fsp,
    // White text beats the dark ink only above alpha ~0.73 (WCAG contrast crossover on a white card).
    hot: alpha > 0.73,
    share: found.count > 0 ? Math.min(1, found.fsp / found.count) : 0,
    style: { background: `rgba(64, 47, 255, ${alpha.toFixed(3)})` },
  }
}

const rows = computed(() =>
  stacksWithPeople.value.map((stack) => ({
    stack,
    cells: GRADE_ORDER.map((grade) => ({ grade, cell: cellOf(stack, grade) })),
  })),
)

function cellTitle(stack: Stack, grade: Grade, cell: Cell): string {
  const name = `${reference.stackTitle(stack)} · ${reference.gradeTitle(grade)}`
  return `${name}: ${formatCount(cell.count, CANDIDATES)}, из них с результатами ФСП — ${cell.fsp}`
}

function cellLink(stack: Stack, grade: Grade) {
  return searchLocation({ ...props.carry, stacks: [stack], grades: [grade] })
}
function stackLink(stack: Stack) {
  return searchLocation({ ...props.carry, stacks: [stack] })
}
function gradeLink(grade: Grade) {
  return searchLocation({ ...props.carry, grades: [grade] })
}
</script>

<template>
  <div class="heat-wrap">
    <table class="heat">
      <caption class="sr-only">
        Кандидаты по стеку и грейду: число кандидатов и сколько из них с результатами ФСП
      </caption>
      <colgroup>
        <col class="heat__col-head" />
        <col v-for="grade in GRADE_ORDER" :key="grade" />
      </colgroup>
      <thead>
        <tr>
          <td class="heat__corner"></td>
          <th v-for="grade in GRADE_ORDER" :key="grade" scope="col" class="heat__col-title">
            <RouterLink class="heat__head-link" :to="gradeLink(grade)" :title="`Все ${reference.gradeTitle(grade)} в поиске`">
              {{ reference.gradeTitle(grade) }}
              <span class="heat__total num">{{ gradeTotals.get(grade) ?? 0 }}</span>
            </RouterLink>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.stack">
          <th scope="row" class="heat__row-title">
            <RouterLink class="heat__head-link heat__head-link--row" :to="stackLink(row.stack)" title="Весь стек в поиске">
              <span class="heat__stack">{{ reference.stackTitle(row.stack) }}</span>
              <span class="heat__total num">{{ stackTotals.get(row.stack) ?? 0 }}</span>
            </RouterLink>
          </th>
          <td v-for="item in row.cells" :key="item.grade" class="heat__td">
            <RouterLink
              v-if="item.cell"
              class="cell"
              :class="{ 'is-hot': item.cell.hot }"
              :style="item.cell.style"
              :to="cellLink(row.stack, item.grade)"
              :title="cellTitle(row.stack, item.grade, item.cell)"
              :aria-label="cellTitle(row.stack, item.grade, item.cell)"
            >
              <span class="cell__count num">{{ item.cell.count }}</span>
              <span class="cell__fsp num">
                <AppIcon name="shield" :size="11" />{{ item.cell.fsp }}<span class="cell__fsp-word">&nbsp;ФСП</span>
              </span>
              <span class="cell__bar" aria-hidden="true">
                <span class="cell__bar-fill" :style="{ width: `${item.cell.share * 100}%` }"></span>
              </span>
            </RouterLink>
            <span v-else class="cell cell--empty" aria-label="Нет кандидатов">·</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="heat__legend">
      <span class="heat__scale" aria-hidden="true"></span>
      <span class="heat__legend-text">Чем темнее ячейка, тем больше кандидатов.</span>
      <span class="heat__legend-text">
        <AppIcon name="shield" :size="12" /> и полоска: сколько из них с результатами ФСП.
      </span>
    </div>

    <p v-if="emptyStacks.length > 0" class="heat__empty">
      Пока нет кандидатов:
      {{ emptyStacks.map((stack) => reference.stackTitle(stack)).join(', ') }}.
    </p>
  </div>
</template>

<style scoped>
.heat-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
}
.heat {
  width: 100%;
  table-layout: fixed;
  border-collapse: separate;
  border-spacing: 4px;
}
.heat__col-head {
  width: 108px;
}
.heat__corner {
  padding: 0;
}
.heat__col-title,
.heat__row-title {
  padding: 0;
  font-weight: 600;
  text-align: left;
  vertical-align: middle;
}
.heat__col-title {
  vertical-align: bottom;
}
.heat__head-link {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 4px 4px 6px;
  border-radius: var(--r-sm);
  color: var(--c-ink);
  font-size: 0.75rem;
  line-height: 1.25;
  text-decoration: none;
}
.heat__head-link:hover {
  color: var(--c-primary);
  background: var(--c-primary-soft);
}
.heat__head-link--row {
  padding: 4px 6px 4px 2px;
  hyphens: auto;
  overflow-wrap: anywhere;
}
.heat__stack {
  min-width: 0;
}
.heat__total {
  font-size: 0.6875rem;
  font-weight: 500;
  color: var(--c-text-muted);
}
.heat__td {
  padding: 0;
}

.cell {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  min-height: 58px;
  padding: 6px 6px 7px;
  border-radius: 8px;
  color: var(--c-ink);
  text-decoration: none;
  transition:
    transform var(--t-fast) var(--ease),
    box-shadow var(--t-fast) var(--ease);
}
.cell:hover {
  color: var(--c-ink);
  transform: translateY(-1px);
  box-shadow: 0 0 0 2px var(--c-primary), var(--shadow-md);
}
.cell.is-hot,
.cell.is-hot:hover {
  color: #fff;
}
.cell__count {
  font-size: 1.0625rem;
  font-weight: 700;
  line-height: 1;
}
.cell__fsp {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 0.6875rem;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}
.cell__fsp-word {
  display: none;
}
.cell__bar {
  position: relative;
  height: 3px;
  border-radius: 2px;
  overflow: hidden;
}
.cell__bar::before {
  content: '';
  position: absolute;
  inset: 0;
  background: currentColor;
  opacity: 0.22;
}
.cell__bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: currentColor;
}
.cell--empty {
  align-items: center;
  background: var(--c-surface-2);
  border: 1px dashed var(--c-border);
  color: var(--c-text-faint);
  font-size: var(--fs-sm);
}

.heat__legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-4);
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.heat__legend-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.heat__scale {
  width: 72px;
  height: 10px;
  border-radius: var(--r-pill);
  background: linear-gradient(90deg, rgba(64, 47, 255, 0.1), rgba(64, 47, 255, 0.95));
}
.heat__empty {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}

@media (max-width: 639px) {
  .heat__col-title .heat__head-link {
    padding-inline: 2px;
    font-size: 0.6875rem;
  }
}

@media (min-width: 640px) {
  .heat {
    border-spacing: 5px;
  }
  .heat__col-head {
    width: 168px;
  }
  .heat__head-link {
    font-size: var(--fs-sm);
  }
  .cell {
    min-height: 68px;
    padding: 8px 10px 9px;
  }
  .cell__count {
    font-size: 1.25rem;
  }
  .cell__fsp {
    font-size: var(--fs-xs);
  }
  .cell__fsp-word {
    display: inline;
  }
}
</style>
