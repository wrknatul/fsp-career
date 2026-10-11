<script setup lang="ts">
import { computed } from 'vue'

import type { Fact, FactKind } from '@/api/types'
import { useReferenceStore } from '@/stores/reference'
import {
  achievementFactValue,
  achievementYear,
  experienceFactValue,
  isHttpUrl,
  isManualAchievement,
  rankFactValue,
  roleFactValue,
  skillFactValue,
  verificationRank,
} from '@/utils/facts'
import { formatDate, formatYears } from '@/utils/format'
import { ACHIEVEMENT_RESULT_TITLES, QUIZ_LEVEL_TITLES } from '@/utils/labels'

import AppButton from './AppButton.vue'
import SourceBadge from './SourceBadge.vue'

// Profile facts grouped by kind, each with the source badge and its evidence.
//   <FactList :facts="profile.facts" />
//   <FactList :facts="profile.facts" :kinds="['achievement']" removable @remove="onRemove" />
// `removable` shows "Удалить" on manually added achievements (source "self"); the page does the request.
const props = withDefaults(
  defineProps<{
    facts: readonly Fact[]
    /** Which groups to show and in what order. Default: all five. */
    kinds?: readonly FactKind[]
    removable?: boolean
    emptyText?: string
  }>(),
  {
    kinds: () => ['achievement', 'rank', 'skill', 'experience', 'role'],
    removable: false,
    emptyText: 'Пока нет ни одного факта. Привяжите ФСП, загрузите резюме или пройдите тест.',
  },
)

const emit = defineEmits<{ remove: [fact: Fact] }>()

const reference = useReferenceStore()

const GROUP_TITLES: Record<FactKind, string> = {
  achievement: 'Достижения',
  rank: 'Разряды и звания',
  skill: 'Навыки',
  experience: 'Опыт работы',
  role: 'Роли',
}

type Entry = {
  fact: Fact
  meta: string
  positions: { key: string; text: string }[]
  link: string | null
  linkLabel: string
  linkHint: string | undefined
  quote: string | null
  removable: boolean
}

function achievementMeta(fact: Fact): string {
  const value = achievementFactValue(fact)
  const parts: string[] = [reference.levelTitle(value.level)]
  if (value.discipline !== null) {
    parts.push(reference.disciplineTitle(value.discipline))
  }
  if (value.place !== null) {
    parts.push(`${value.place} место`)
  } else {
    parts.push(ACHIEVEMENT_RESULT_TITLES[value.result].toLowerCase())
  }
  const year = achievementYear(fact)
  if (year !== null) {
    parts.push(String(year))
  }
  if (value.team_name !== null) {
    parts.push(`команда «${value.team_name}»`)
  }
  return parts.join(' · ')
}

function metaOf(fact: Fact): string {
  switch (fact.kind) {
    case 'achievement':
      return achievementMeta(fact)
    case 'rank': {
      const value = rankFactValue(fact)
      const parts: string[] = []
      if (value.discipline !== null) parts.push(reference.disciplineTitle(value.discipline))
      if (value.assigned_at !== null) parts.push(`присвоен ${formatDate(value.assigned_at)}`)
      if (value.order_no !== null) parts.push(`приказ ${value.order_no}`)
      return parts.join(' · ')
    }
    case 'skill': {
      const value = skillFactValue(fact)
      // Level names (Базовый/Уверенный/Продвинутый) belong to platform tests; other sources get the bare number.
      const base = `Уровень ${value.level} из 3`
      return fact.source === 'test' ? `${base} · ${QUIZ_LEVEL_TITLES[value.level].toLowerCase()}` : base
    }
    case 'experience': {
      const value = experienceFactValue(fact)
      return value.years > 0 ? `Всего ${formatYears(value.years)}` : ''
    }
    case 'role':
      return roleFactValue(fact).reason
  }
}

function toEntry(fact: Fact): Entry {
  const positions =
    fact.kind === 'experience'
      ? experienceFactValue(fact).positions.map((position, index) => ({
          key: `${fact.id}-${index}`,
          text: [
            position.title,
            position.company,
            position.period,
            position.years > 0 ? formatYears(position.years) : null,
          ]
            .filter((part): part is string => typeof part === 'string' && part !== '')
            .join(' · '),
        }))
      : []
  const evidence = fact.evidence
  const evidenceIsLink = evidence !== null && isHttpUrl(evidence)
  return {
    fact,
    meta: metaOf(fact),
    positions,
    link: evidenceIsLink ? evidence : null,
    linkLabel: fact.source === 'fsp' ? 'Протокол соревнования' : 'Подтверждающий документ',
    linkHint:
      fact.source === 'fsp' && reference.isMock
        ? 'Демо-стенд: адрес протокола вымышленный, страница не откроется'
        : undefined,
    quote: evidence !== null && !evidenceIsLink && evidence !== '' ? evidence : null,
    removable: props.removable && isManualAchievement(fact),
  }
}

function sortFacts(kind: FactKind, list: Fact[]): Fact[] {
  const sorted = [...list]
  if (kind === 'achievement') {
    // Newest first, then the stronger confirmation first.
    sorted.sort(
      (a, b) =>
        (achievementYear(b) ?? 0) - (achievementYear(a) ?? 0) ||
        verificationRank(b.verification) - verificationRank(a.verification),
    )
  } else if (kind === 'skill') {
    // Higher level first, then the stronger confirmation, then alphabetically.
    sorted.sort(
      (a, b) =>
        skillFactValue(b).level - skillFactValue(a).level ||
        verificationRank(b.verification) - verificationRank(a.verification) ||
        a.title.localeCompare(b.title, 'ru'),
    )
  }
  return sorted
}

const groups = computed(() =>
  props.kinds
    .map((kind) => {
      const list = props.facts.filter((fact) => fact.kind === kind)
      return { kind, title: GROUP_TITLES[kind], entries: sortFacts(kind, list).map(toEntry) }
    })
    .filter((group) => group.entries.length > 0),
)
</script>

<template>
  <div class="facts">
    <p v-if="groups.length === 0" class="facts__empty">{{ emptyText }}</p>

    <section v-for="group in groups" :key="group.kind" class="facts__group">
      <h3 class="section-title">{{ group.title }} <span class="facts__count num">{{ group.entries.length }}</span></h3>
      <ul class="facts__list">
        <li v-for="entry in group.entries" :key="entry.fact.id" class="fact">
          <div class="fact__main">
            <p class="fact__title">{{ entry.fact.title }}</p>
            <p v-if="entry.meta" class="fact__meta">{{ entry.meta }}</p>
            <ul v-if="entry.positions.length > 0" class="fact__positions">
              <li v-for="position in entry.positions" :key="position.key">{{ position.text }}</li>
            </ul>
            <p v-if="entry.quote" class="fact__quote">«{{ entry.quote }}»</p>
            <a
              v-if="entry.link"
              class="fact__link"
              :href="entry.link"
              :title="entry.linkHint"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ entry.linkLabel }}
            </a>
          </div>
          <div class="fact__side">
            <SourceBadge :verification="entry.fact.verification" size="sm" />
            <AppButton
              v-if="entry.removable"
              variant="ghost"
              size="sm"
              :aria-label="`Удалить: ${entry.fact.title}`"
              @click="emit('remove', entry.fact)"
            >
              Удалить
            </AppButton>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.facts {
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
}
.facts__empty {
  color: var(--c-text-muted);
  line-height: 1.55;
}
.facts__group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.facts__count {
  font-weight: 500;
  color: var(--c-text-muted);
}
.facts__list {
  list-style: none;
  display: flex;
  flex-direction: column;
}
.fact {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--c-border);
}
.fact:last-child {
  border-bottom: 0;
}
.fact__main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.fact__title {
  font-weight: 600;
  line-height: 1.4;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.fact__meta {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.fact__positions {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 2px;
  padding-left: var(--sp-3);
  border-left: 2px solid var(--c-border);
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.fact__quote {
  font-size: var(--fs-sm);
  font-style: italic;
  color: var(--c-text-muted);
  overflow-wrap: anywhere;
}
.fact__link {
  align-self: flex-start;
  font-size: var(--fs-sm);
  font-weight: 500;
}
.fact__side {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
}

@media (min-width: 640px) {
  .fact {
    flex-direction: row;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--sp-5);
  }
  .fact__side {
    flex: none;
    justify-content: flex-end;
    max-width: 45%;
  }
}
</style>
