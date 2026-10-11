<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'

import type { CandidateMatch } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ScoreRing from '@/components/ScoreRing.vue'
import SkillChip from '@/components/SkillChip.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import { useReferenceStore } from '@/stores/reference'
import { formatMoney, formatYears } from '@/utils/format'

import OfferStatusBadge from './OfferStatusBadge.vue'
import ScoreBreakdown from './ScoreBreakdown.vue'

// One search result: who the candidate is, how well they fit and, above all, what confirms it.
//   <MatchCard :match="item" :vacancy-id="filters.vacancy_id" />
const props = withDefaults(defineProps<{ match: CandidateMatch; vacancyId?: number | null }>(), { vacancyId: null })

const reference = useReferenceStore()

const candidate = computed(() => props.match.candidate)
const category = computed(() => candidate.value.category)

function cardLocation(openOfferForm: boolean): RouteLocationRaw {
  const query: Record<string, string> = {}
  if (props.vacancyId !== null) {
    query.vacancy_id = String(props.vacancyId)
  }
  if (openOfferForm) {
    query.offer = '1'
  }
  return { name: 'employer-candidate', params: { id: String(candidate.value.id) }, query }
}

const cardLink = computed(() => cardLocation(false))
const offerLink = computed(() => cardLocation(true))

const subline = computed(() => {
  const parts: string[] = []
  if (candidate.value.city) {
    parts.push(candidate.value.city)
  }
  if (candidate.value.relocation) {
    parts.push('готов к переезду')
  }
  if (category.value.experience_years > 0) {
    parts.push(`опыт ${formatYears(category.value.experience_years)}`)
  }
  return parts.join(' · ')
})

const confirmationMarks = computed(() => {
  if (category.value.stack === null) {
    return []
  }
  return [
    { key: 'stack', ok: category.value.stack_confirmed, text: category.value.stack_confirmed ? 'Стек подтверждён' : 'Стек не подтверждён' },
    { key: 'grade', ok: category.value.grade_confirmed, text: category.value.grade_confirmed ? 'Грейд подтверждён' : 'Грейд не подтверждён' },
  ]
})

const hasSkillBlocks = computed(() => props.match.matched_skills.length > 0 || props.match.missing_skills.length > 0)
const strongSkills = computed(() => category.value.top_skills.slice(0, 5))
const achievements = computed(() => props.match.top_achievements.slice(0, 3))

function achievementMeta(index: number): string {
  const item = achievements.value[index]
  const parts: string[] = [reference.levelTitle(item.level)]
  if (item.place !== null) {
    parts.push(`${item.place} место`)
  }
  if (item.year !== null) {
    parts.push(String(item.year))
  }
  return parts.join(' · ')
}
</script>

<template>
  <article class="match card" :aria-label="`Кандидат ${candidate.display_name}`">
    <header class="match__head">
      <ScoreRing :value="match.score" :size="76" caption="из 100" />

      <div class="match__who">
        <h3 class="match__name">
          <RouterLink class="match__name-link" :to="cardLink">{{ candidate.display_name }}</RouterLink>
        </h3>
        <p v-if="subline" class="match__sub">{{ subline }}</p>
        <p class="match__category">{{ category.label }}</p>
        <p v-if="match.score === null" class="match__unscored">Без оценки: отсортировано по опыту и достижениям</p>
      </div>
    </header>

    <div class="match__tags">
      <span
        v-for="mark in confirmationMarks"
        :key="mark.key"
        class="mark"
        :class="mark.ok ? 'mark--ok' : 'mark--warn'"
      >
        <AppIcon :name="mark.ok ? 'check' : 'alert'" :size="12" />{{ mark.text }}
      </span>
      <SourceBadge v-if="candidate.fsp_linked" verification="verified" size="sm" />
      <span v-if="candidate.sport_rank" class="rank num" title="Спортивный разряд по реестру ФСП">
        {{ reference.rankTitle(candidate.sport_rank) }}
      </span>
      <OfferStatusBadge v-if="match.offer_status" :status="match.offer_status" prefix="Оффер:" />
    </div>

    <section class="match__block" aria-label="Из чего складывается оценка">
      <h4 class="match__label">Из чего складывается оценка</h4>
      <ScoreBreakdown :components="match.components" />
    </section>

    <section v-if="hasSkillBlocks" class="match__block" aria-label="Навыки по запросу">
      <div v-if="match.matched_skills.length > 0" class="match__skills">
        <h4 class="match__label">Совпали с запросом</h4>
        <div class="chips">
          <SkillChip
            v-for="skill in match.matched_skills"
            :key="skill.skill"
            :title="skill.title"
            :verification="skill.verification"
            :evidence="skill.evidence"
          />
        </div>
      </div>
      <div v-if="match.missing_skills.length > 0" class="match__skills">
        <h4 class="match__label">Нет у кандидата</h4>
        <div class="chips">
          <SkillChip v-for="skill in match.missing_skills" :key="skill.skill" :title="skill.title" missing />
        </div>
      </div>
    </section>

    <section v-else-if="strongSkills.length > 0" class="match__block" aria-label="Сильные стороны профиля">
      <h4 class="match__label">Лучше всего подтверждено</h4>
      <div class="chips">
        <SkillChip
          v-for="skill in strongSkills"
          :key="skill.skill"
          :title="skill.title"
          :verification="skill.verification"
          :evidence="skill.evidence"
        />
      </div>
    </section>

    <section class="match__block" aria-label="Достижения">
      <h4 class="match__label">Достижения</h4>
      <ul v-if="achievements.length > 0" class="achievements">
        <li v-for="(item, index) in achievements" :key="`${item.title}-${index}`" class="achievement">
          <div class="achievement__text">
            <span class="achievement__title">{{ item.title }}</span>
            <span class="achievement__meta">{{ achievementMeta(index) }}</span>
          </div>
          <SourceBadge :verification="item.verification" size="sm" />
        </li>
      </ul>
      <p v-else class="match__none">В профиле пока нет достижений.</p>
    </section>

    <section v-if="match.reasons.length > 0" class="match__block" aria-label="Почему кандидат в выдаче">
      <h4 class="match__label">Почему в выдаче</h4>
      <ul class="reasons">
        <li v-for="(reason, index) in match.reasons" :key="index">{{ reason }}</li>
      </ul>
    </section>

    <footer class="match__foot">
      <p class="match__salary">
        <span class="muted">Ожидания</span>
        <span v-if="candidate.salary_expectation !== null" class="num match__salary-value">
          {{ formatMoney(candidate.salary_expectation) }}
        </span>
        <span v-else class="muted">не указаны</span>
      </p>
      <div class="match__actions">
        <AppButton variant="secondary" size="sm" :to="cardLink">Открыть карточку</AppButton>
        <!-- An offer is unique per (vacancy, candidate), so after one offer the way to another vacancy stays open. -->
        <AppButton :variant="match.offer_status === null ? 'primary' : 'ghost'" size="sm" :to="offerLink">
          {{ match.offer_status === null ? 'Отправить оффер' : 'Оффер по другой вакансии' }}
        </AppButton>
      </div>
    </footer>
  </article>
</template>

<style scoped>
.match {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
}
.match__head {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-4);
}
.match__who {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}
.match__name {
  font-size: var(--fs-lg);
  letter-spacing: -0.03em;
}
.match__name-link {
  color: var(--c-ink);
  text-decoration: none;
}
.match__name-link:hover {
  color: var(--c-primary);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.match__sub {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.match__category {
  margin-top: 2px;
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--c-ink);
  line-height: 1.35;
}
.match__unscored {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  line-height: 1.4;
}

.match__tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.mark {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px 2px 7px;
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 600;
  line-height: 1.35;
  white-space: nowrap;
}
.mark--ok {
  background: var(--c-success-soft);
  color: var(--c-success-text);
}
.mark--warn {
  background: var(--c-warning-soft);
  color: var(--c-warning-text);
}
.rank {
  padding: 2px 9px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-ink);
}

.match__block {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
}
.match__skills {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.match__label {
  font-family: var(--font-sans);
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.match__none {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}

.achievements {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  list-style: none;
}
.achievement {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
}
.achievement__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.achievement__title {
  font-size: var(--fs-sm);
  font-weight: 600;
  line-height: 1.35;
  overflow-wrap: break-word;
}
.achievement__meta {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.achievement :deep(.badge) {
  flex: none;
}
@media (max-width: 479px) {
  /* The badge is wide: under the text instead of squeezing the title. */
  .achievement {
    flex-direction: column;
    gap: 4px;
  }
}

.reasons {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-left: 18px;
  font-size: var(--fs-sm);
  color: var(--c-text);
}
.reasons li::marker {
  color: var(--c-primary);
}

.match__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3) var(--sp-4);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
}
.match__salary {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
}
.match__salary-value {
  font-weight: 600;
  color: var(--c-ink);
}
.match__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}
@media (max-width: 479px) {
  .match__actions {
    width: 100%;
  }
  .match__actions > * {
    flex: 1;
  }
}
</style>
