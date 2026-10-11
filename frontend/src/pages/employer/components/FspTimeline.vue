<script setup lang="ts">
import { computed } from 'vue'

import type { Fact } from '@/api/types'
import AppIcon from '@/components/AppIcon.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import { isHiddenEvidence } from '@/pages/employer/redaction'
import { useReferenceStore } from '@/stores/reference'
import { achievementFactValue, achievementYear, isHttpUrl } from '@/utils/facts'
import { ACHIEVEMENT_RESULT_TITLES } from '@/utils/labels'

// Results from the FSP registry as a ribbon by years, the newest first. Every result keeps its badge
// and a link to the competition protocol: the employer sees what exactly confirms the candidate.
//   <FspTimeline :facts="fspAchievements" />
const props = defineProps<{ facts: readonly Fact[] }>()

const reference = useReferenceStore()

type Entry = {
  id: number
  title: string
  meta: string
  place: number | null
  link: string | null
  /** The protocol URL exists but the backend hid it: it opens when the candidate accepts an offer. */
  linkHidden: boolean
}

type YearGroup = { key: string; label: string; entries: Entry[] }

function metaOf(fact: Fact): string {
  const value = achievementFactValue(fact)
  const parts: string[] = [reference.levelTitle(value.level)]
  if (value.discipline !== null) {
    parts.push(reference.disciplineTitle(value.discipline))
  }
  if (value.team_name !== null) {
    parts.push(`команда «${value.team_name}»`)
  }
  if (value.participants_total !== null) {
    parts.push(`участников: ${value.participants_total}`)
  }
  if (value.place === null) {
    parts.push(ACHIEVEMENT_RESULT_TITLES[value.result].toLowerCase())
  }
  return parts.join(' · ')
}

const groups = computed<YearGroup[]>(() => {
  const byYear = new Map<number | null, Fact[]>()
  for (const fact of props.facts) {
    const year = achievementYear(fact)
    byYear.set(year, [...(byYear.get(year) ?? []), fact])
  }
  const years = [...byYear.keys()].sort((a, b) => {
    if (a === null) return 1
    if (b === null) return -1
    return b - a
  })
  return years.map((year) => ({
    key: String(year),
    label: year === null ? 'Без даты' : String(year),
    entries: (byYear.get(year) ?? [])
      .map((fact) => {
        const value = achievementFactValue(fact)
        return {
          id: fact.id,
          title: fact.title,
          meta: metaOf(fact),
          place: value.place,
          link: fact.evidence !== null && isHttpUrl(fact.evidence) ? fact.evidence : null,
          linkHidden: isHiddenEvidence(fact.evidence),
        }
      })
      .sort((a, b) => (a.place ?? 999) - (b.place ?? 999)),
  }))
})

const protocolHint = computed(() =>
  reference.isMock ? 'Демо-стенд: адрес протокола вымышленный, страница не откроется' : undefined,
)
</script>

<template>
  <section class="timeline card" aria-labelledby="fsp-timeline-title">
    <header class="timeline__head">
      <h2 id="fsp-timeline-title" class="timeline__title">Результаты ФСП</h2>
      <SourceBadge verification="verified" size="sm" />
      <span class="timeline__count num">{{ facts.length }}</span>
    </header>

    <ol class="timeline__years">
      <li v-for="group in groups" :key="group.key" class="year">
        <h3 class="year__label num">{{ group.label }}</h3>
        <ul class="year__items">
          <li v-for="entry in group.entries" :key="entry.id" class="result">
            <span v-if="entry.place !== null" class="result__place" :class="{ 'is-top': entry.place <= 3 }">
              <span class="num">{{ entry.place }}</span>
              <span class="result__place-word">место</span>
            </span>
            <div class="result__text">
              <p class="result__title">{{ entry.title }}</p>
              <p class="result__meta">{{ entry.meta }}</p>
              <a
                v-if="entry.link"
                class="result__link"
                :href="entry.link"
                :title="protocolHint"
                target="_blank"
                rel="noopener noreferrer"
              >
                Протокол соревнования
              </a>
              <p v-else-if="entry.linkHidden" class="result__locked">
                <AppIcon name="lock" :size="12" />
                Ссылка на протокол откроется после принятия оффера
              </p>
            </div>
          </li>
        </ul>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.timeline {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.timeline__head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.timeline__title {
  font-size: var(--fs-lg);
}
.timeline__count {
  margin-left: auto;
  color: var(--c-text-muted);
  font-size: var(--fs-sm);
}
.timeline__years {
  display: flex;
  flex-direction: column;
  list-style: none;
}
.year {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: var(--sp-3);
}
.year__label {
  padding-top: 12px;
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--c-primary);
}
.year__items {
  position: relative;
  display: flex;
  flex-direction: column;
  padding-left: var(--sp-4);
  border-left: 2px solid var(--c-primary-soft-2);
  list-style: none;
}
.result {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--c-border);
}
.result:last-child {
  border-bottom: 0;
}
.result::before {
  content: '';
  position: absolute;
  top: 20px;
  left: calc(var(--sp-4) * -1 - 6px);
  width: 10px;
  height: 10px;
  border: 2px solid var(--c-primary);
  border-radius: 50%;
  background: var(--c-surface);
}
.result__place {
  display: flex;
  flex: none;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 48px;
  padding: 4px 0;
  border-radius: var(--r-md);
  background: var(--c-neutral-soft);
  color: var(--c-ink);
  line-height: 1.1;
}
.result__place.is-top {
  background: var(--c-primary);
  color: #fff;
}
.result__place .num {
  font-size: var(--fs-md);
  font-weight: 700;
}
.result__place-word {
  font-size: 0.625rem;
  opacity: 0.85;
}
.result__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.result__title {
  font-size: var(--fs-sm);
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.result__meta {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  line-height: 1.45;
}
.result__link {
  width: fit-content;
  font-size: var(--fs-xs);
  font-weight: 600;
}
.result__locked {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  line-height: 1.45;
}
</style>
