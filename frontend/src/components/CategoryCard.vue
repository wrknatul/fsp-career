<script setup lang="ts">
import { computed } from 'vue'

import type { Category } from '@/api/types'
import { useReferenceStore } from '@/stores/reference'
import { formatScore, formatYears } from '@/utils/format'

import AppIcon from './AppIcon.vue'
import SkillChip from './SkillChip.vue'

// The category of a candidate: stack, grade, team role, work formats.
// Unconfirmed stack/grade carry an explicit "не подтверждён" mark; grade_note is shown as a note.
//   <CategoryCard :category="profile.category" title="Ваша категория" show-skills />
// Slots: "undetermined" (calls to action when the stack is null), "footer".
const props = withDefaults(
  defineProps<{
    category: Category
    title?: string
    /** Also list top_skills as chips. */
    showSkills?: boolean
  }>(),
  { title: 'Категория', showSkills: false },
)

const reference = useReferenceStore()

const isDetermined = computed(() => props.category.stack !== null)
const formats = computed(() =>
  props.category.work_formats.length > 0
    ? reference.joinTitles(props.category.work_formats, reference.workFormatTitle)
    : 'Не указан',
)
</script>

<template>
  <section class="cat card" :aria-label="title">
    <header class="cat__head">
      <p class="eyebrow">{{ title }}</p>
      <p class="cat__label">{{ category.label }}</p>
    </header>

    <template v-if="isDetermined">
      <dl class="cat__grid">
        <div class="cat__cell">
          <dt>Стек</dt>
          <dd class="cat__value">{{ reference.stackTitle(category.stack) }}</dd>
          <span v-if="category.stack_confirmed" class="mark mark--ok"><AppIcon name="check" :size="12" />подтверждён</span>
          <span v-else class="mark mark--warn"><AppIcon name="alert" :size="12" />стек не подтверждён</span>
        </div>

        <div class="cat__cell">
          <dt>Грейд</dt>
          <dd class="cat__value">
            {{ reference.gradeTitle(category.grade) }}
            <span class="cat__points num" title="Баллы грейда">{{ formatScore(category.grade_points) }}</span>
          </dd>
          <span v-if="category.grade_confirmed" class="mark mark--ok"><AppIcon name="check" :size="12" />подтверждён</span>
          <span v-else class="mark mark--warn"><AppIcon name="alert" :size="12" />грейд не подтверждён</span>
        </div>

        <div class="cat__cell">
          <dt>Роль в команде</dt>
          <dd class="cat__value">{{ reference.teamRoleTitle(category.team_role) }}</dd>
          <span v-if="category.team_role_source === 'resume'" class="mark mark--neutral">по резюме</span>
        </div>

        <div class="cat__cell">
          <dt>Формат работы</dt>
          <dd class="cat__value">{{ formats }}</dd>
          <span v-if="category.experience_years > 0" class="mark mark--neutral">
            опыт {{ formatYears(category.experience_years) }}
          </span>
        </div>
      </dl>

      <p v-if="category.grade_note" class="cat__note">
        <AppIcon name="info" :size="16" />
        <span>{{ category.grade_note }}</span>
      </p>

      <div v-if="showSkills && category.top_skills.length > 0" class="cat__skills">
        <p class="cat__skills-title">Навыки с подтверждением</p>
        <div class="cat__chips">
          <SkillChip
            v-for="skill in category.top_skills"
            :key="skill.skill"
            :title="skill.title"
            :verification="skill.verification"
            :evidence="skill.evidence"
          />
        </div>
      </div>
    </template>

    <div v-else class="cat__undetermined">
      <p class="cat__undetermined-text">
        Категория пока не определена. Платформа ставит стек и грейд только по подтверждаемым источникам:
        привязка к ФСП, экспресс-тест или резюме.
      </p>
      <slot name="undetermined" />
    </div>

    <footer v-if="$slots.footer" class="cat__footer"><slot name="footer" /></footer>
  </section>
</template>

<style scoped>
.cat {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  position: relative;
  overflow: hidden;
}
/* A thin accent edge: the one place where the brand colour is a fill. */
.cat::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--c-primary);
}
.cat__head {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cat__label {
  font-family: var(--font-mono);
  font-size: clamp(1.125rem, 1rem + 0.9vw, 1.5rem);
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.2;
  color: var(--c-ink);
  text-wrap: balance;
}
/* Columns follow the card width (not the viewport): the card may sit in a half-width column. */
.cat__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: var(--sp-4) var(--sp-5);
  margin: 0;
}
.cat__cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
}
.cat__cell dt {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.cat__value {
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--c-ink);
  overflow-wrap: break-word;
}
.cat__points {
  margin-left: 6px;
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--c-text-muted);
}
.mark {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 600;
  line-height: 1.4;
}
.mark--ok {
  background: var(--c-success-soft);
  color: var(--c-success-text);
}
.mark--warn {
  background: var(--c-warning-soft);
  color: var(--c-warning-text);
}
.mark--neutral {
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
}
.cat__note {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: var(--r-md);
  background: var(--c-primary-soft);
  color: var(--c-ink);
  font-size: var(--fs-sm);
  line-height: 1.5;
}
.cat__note :deep(svg) {
  margin-top: 2px;
  color: var(--c-primary);
}
.cat__skills {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.cat__skills-title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-text-muted);
}
.cat__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cat__undetermined {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-4);
}
.cat__undetermined-text {
  max-width: 56ch;
  color: var(--c-text-muted);
  line-height: 1.55;
}
.cat__footer {
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
}
</style>
