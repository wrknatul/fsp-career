<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import { addAchievement, deleteAchievement } from '@/api/candidate'
import { fieldErrors } from '@/api/client'
import type { AchievementResult, CandidateProfile, CompetitionLevel, Discipline, Fact } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppInput from '@/components/AppInput.vue'
import AppSelect from '@/components/AppSelect.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { achievementFactValue, achievementYear, isHttpUrl, isManualAchievement } from '@/utils/facts'
import { ACHIEVEMENT_RESULT_TITLES } from '@/utils/labels'

// Achievements outside the FSP registry (olympiads, hackathons, CTF): always "declared", 35% of the weight.
const props = defineProps<{ profile: CandidateProfile }>()
const emit = defineEmits<{ updated: [profile: CandidateProfile] }>()

const reference = useReferenceStore()
const toast = useToastStore()

const MIN_YEAR = 1990
const currentYear = new Date().getFullYear()

type FormState = {
  title: string
  year: number | null
  level: CompetitionLevel | null
  result: AchievementResult
  discipline: Discipline | null
  document_url: string
}

function blank(): FormState {
  return { title: '', year: currentYear, level: null, result: 'participant', discipline: null, document_url: '' }
}

const form = reactive<FormState>(blank())
const errors = reactive<Record<string, string>>({})
const saving = ref(false)
const removeTarget = ref<Fact | null>(null)
const askRemove = ref(false)
const removing = ref(false)

const resultOptions: { value: AchievementResult; label: string }[] = [
  { value: 'winner', label: ACHIEVEMENT_RESULT_TITLES.winner },
  { value: 'prize', label: ACHIEVEMENT_RESULT_TITLES.prize },
  { value: 'participant', label: ACHIEVEMENT_RESULT_TITLES.participant },
]

const manual = computed(() =>
  props.profile.facts
    .filter(isManualAchievement)
    .map((fact) => {
      const value = achievementFactValue(fact)
      const parts: string[] = [reference.levelTitle(value.level)]
      if (value.discipline !== null) parts.push(reference.disciplineTitle(value.discipline))
      parts.push(ACHIEVEMENT_RESULT_TITLES[value.result])
      const year = achievementYear(fact)
      if (year !== null) parts.push(String(year))
      return { fact, title: value.title, meta: parts.join(' · '), link: isHttpUrl(value.document_url) ? value.document_url : null }
    })
    .sort((a, b) => (achievementYear(b.fact) ?? 0) - (achievementYear(a.fact) ?? 0)),
)

function clearErrors(): void {
  for (const key of Object.keys(errors)) {
    delete errors[key]
  }
}

function validate(): boolean {
  clearErrors()
  const title = form.title.trim()
  if (title.length < 3) {
    errors.title = 'Название — не короче трёх символов'
  } else if (title.length > 200) {
    errors.title = 'Название — не длиннее 200 символов'
  }
  if (form.year === null || !Number.isInteger(form.year) || form.year < MIN_YEAR || form.year > currentYear) {
    errors.year = `Год — от ${MIN_YEAR} до ${currentYear}`
  }
  if (form.level === null) {
    errors.level = 'Выберите уровень'
  }
  const url = form.document_url.trim()
  if (url !== '' && !isHttpUrl(url)) {
    errors.document_url = 'Ссылка должна начинаться с http:// или https://'
  }
  return Object.keys(errors).length === 0
}

async function submit(): Promise<void> {
  if (saving.value || !validate() || form.year === null || form.level === null) {
    return
  }
  saving.value = true
  try {
    const url = form.document_url.trim()
    const next = await addAchievement({
      title: form.title.trim(),
      year: form.year,
      level: form.level,
      result: form.result,
      discipline: form.discipline,
      document_url: url === '' ? null : url,
    })
    emit('updated', next)
    Object.assign(form, blank())
    toast.success('Добавлено. Не подтверждено: вклад в грейд — 35%')
  } catch (err) {
    const fields = fieldErrors(err)
    const entries = Object.entries(fields)
    for (const [field, message] of entries) {
      errors[field] = message
    }
    if (entries.length === 0) {
      toast.fromError(err)
    }
  } finally {
    saving.value = false
  }
}

function askToRemove(fact: Fact): void {
  removeTarget.value = fact
  askRemove.value = true
}

async function remove(): Promise<void> {
  const target = removeTarget.value
  if (target === null || removing.value) {
    return
  }
  removing.value = true
  try {
    emit('updated', await deleteAchievement(target.id))
    askRemove.value = false
    toast.info('Достижение удалено')
  } catch (err) {
    toast.fromError(err)
  } finally {
    removing.value = false
  }
}
</script>

<template>
  <section id="achievements" class="ach card" aria-labelledby="ach-title">
    <header class="ach__head">
      <h2 id="ach-title" class="h3">Достижения вручную</h2>
      <p class="ach__sub">
        Олимпиады, хакатоны, CTF вне реестра ФСП. Проверить их платформа не может, поэтому они помечаются
        <SourceBadge verification="declared" size="sm" /> и дают в грейд 35% веса подтверждённого.
      </p>
    </header>

    <form class="ach__form" novalidate @submit.prevent="submit">
      <AppInput
        v-model="form.title"
        label="Название"
        required
        placeholder="Например: Всероссийская олимпиада школьников по информатике"
        :maxlength="200"
        :error="errors.title"
      />
      <div class="ach__grid">
        <AppInput
          v-model="form.year"
          label="Год"
          type="number"
          required
          inputmode="numeric"
          :min="MIN_YEAR"
          :max="currentYear"
          :error="errors.year"
        />
        <AppSelect
          v-model="form.level"
          label="Уровень"
          required
          placeholder="Выберите уровень"
          :options="reference.levelOptions"
          :error="errors.level"
        />
      </div>
      <SegmentedControl v-model="form.result" :options="resultOptions" label="Результат" block />
      <AppSelect
        v-model="form.discipline"
        label="Дисциплина"
        placeholder="Не относится к дисциплинам ФСП"
        :options="reference.disciplineOptions"
        :error="errors.discipline"
        hint="Если выбрать дисциплину, она учтётся в навыках и поиске."
      />
      <AppInput
        v-model="form.document_url"
        label="Ссылка на диплом или протокол"
        type="url"
        placeholder="https://"
        :maxlength="500"
        :error="errors.document_url"
        hint="Необязательно. Ссылка не делает факт подтверждённым, но работодателю будет проще проверить."
      />
      <div>
        <AppButton type="submit" :loading="saving">Добавить достижение</AppButton>
      </div>
    </form>

    <div class="ach__list-wrap">
      <h3 class="section-title">Добавлено вами <span class="ach__count num">{{ manual.length }}</span></h3>
      <p v-if="manual.length === 0" class="ach__empty">Пока ничего. Добавленное появится здесь и в общем списке фактов ниже.</p>
      <ul v-else class="ach__list">
        <li v-for="item in manual" :key="item.fact.id" class="ach__item">
          <div class="ach__main">
            <p class="ach__title">{{ item.title }}</p>
            <p class="ach__meta">{{ item.meta }}</p>
            <p class="ach__note">Не подтверждено. Вклад в грейд — 35%</p>
            <a v-if="item.link" class="ach__link" :href="item.link" target="_blank" rel="noopener noreferrer">
              Подтверждающий документ
            </a>
          </div>
          <div class="ach__side">
            <SourceBadge :verification="item.fact.verification" size="sm" />
            <AppButton variant="ghost" size="sm" :aria-label="`Удалить: ${item.title}`" @click="askToRemove(item.fact)">
              Удалить
            </AppButton>
          </div>
        </li>
      </ul>
    </div>

    <ConfirmModal
      v-model="askRemove"
      title="Удалить достижение?"
      :message="removeTarget ? `«${removeTarget.title}» пропадёт из профиля, грейд пересчитается.` : ''"
      confirm-label="Удалить"
      danger
      :loading="removing"
      @confirm="remove"
    />
  </section>
</template>

<style scoped>
.ach {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  scroll-margin-top: 80px;
}
.ach__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ach__sub {
  font-size: var(--fs-sm);
  line-height: 1.7;
  color: var(--c-text-muted);
}
.ach__form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.ach__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
}
.ach__list-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
}
.ach__count {
  font-weight: 500;
  color: var(--c-text-faint);
}
.ach__empty {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.ach__list {
  list-style: none;
  display: flex;
  flex-direction: column;
}
.ach__item {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--c-border);
}
.ach__item:last-child {
  border-bottom: 0;
}
.ach__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.ach__title {
  font-weight: 600;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.ach__meta {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.ach__note {
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-warning-text);
}
.ach__link {
  align-self: flex-start;
  font-size: var(--fs-sm);
  font-weight: 500;
}
.ach__side {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
}

@media (min-width: 560px) {
  .ach__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .ach__item {
    flex-direction: row;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--sp-5);
  }
  .ach__side {
    flex: none;
  }
}
</style>
