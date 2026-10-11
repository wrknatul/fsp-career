<script setup lang="ts">
import { computed } from 'vue'

import type { Vacancy } from '@/api/types'
import AppCheckbox from '@/components/AppCheckbox.vue'
import AppInput from '@/components/AppInput.vue'
import AppSelect from '@/components/AppSelect.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import SkillPicker from '@/components/SkillPicker.vue'
import { useReferenceStore } from '@/stores/reference'
import { MAX_SALARY, type SearchFilters } from '@/pages/employer/searchFilters'

// The filter form of the search page. It does not hold state: it shows `filters` and reports every
// change as a patch, the page decides when to apply it.
//   <SearchFilterPanel :filters="draft" :vacancies="vacancies" @update="patch" />
const props = defineProps<{
  filters: SearchFilters
  vacancies: readonly Vacancy[]
  /** The list of own vacancies could not be loaded. */
  vacanciesFailed?: boolean
}>()

const emit = defineEmits<{ update: [patch: Partial<SearchFilters>] }>()

const reference = useReferenceStore()

const vacancyOptions = computed(() =>
  props.vacancies
    .filter((vacancy) => vacancy.is_active || vacancy.id === props.filters.vacancy_id)
    .map((vacancy) => ({ value: vacancy.id, label: vacancy.is_active ? vacancy.title : `${vacancy.title} (в архиве)` })),
)

// A city that came from the address bar may be missing from the dictionary: keep it selectable.
const cityOptions = computed(() => {
  const options = [...reference.cityOptions]
  const current = props.filters.city
  if (current !== null && !options.some((option) => option.value === current)) {
    options.unshift({ value: current, label: current })
  }
  return options
})

const salaryMax = computed<number | null>({
  get: () => props.filters.salary_max,
  set: (value) => {
    const clean = value === null || !Number.isFinite(value) || value <= 0 ? null : Math.min(MAX_SALARY, Math.round(value))
    emit('update', { salary_max: clean })
  },
})

const vacancyId = computed<number | null>({
  get: () => props.filters.vacancy_id,
  set: (value) => emit('update', { vacancy_id: value }),
})

const city = computed<string | null>({
  get: () => props.filters.city,
  set: (value) => emit('update', { city: value }),
})
</script>

<template>
  <div class="panel">
    <section class="panel__group">
      <h3 class="section-title">Вакансия</h3>
      <AppSelect
        v-model="vacancyId"
        :options="vacancyOptions"
        label="Подобрать под вакансию"
        placeholder="Без привязки к вакансии"
        :hint="
          vacanciesFailed
            ? 'Не удалось загрузить ваши вакансии, обновите страницу.'
            : vacancyOptions.length === 0
              ? 'Заведите вакансию, и поиск сам возьмёт из неё стек, навыки и бюджет.'
              : 'Стек, грейд, навыки, формат и бюджет вакансии дополнят ваш запрос.'
        "
      />
    </section>

    <section class="panel__group">
      <h3 class="section-title">Категория</h3>
      <ChipSelect
        :model-value="filters.stacks"
        :options="reference.stackOptions"
        label="Стек"
        @update:model-value="emit('update', { stacks: $event })"
      />
      <ChipSelect
        :model-value="filters.grades"
        :options="reference.gradeOptions"
        label="Грейд"
        @update:model-value="emit('update', { grades: $event })"
      />
      <ChipSelect
        :model-value="filters.team_roles"
        :options="reference.teamRoleOptions"
        label="Роль в команде"
        @update:model-value="emit('update', { team_roles: $event })"
      />
      <ChipSelect
        :model-value="filters.work_formats"
        :options="reference.workFormatOptions"
        label="Формат работы"
        @update:model-value="emit('update', { work_formats: $event })"
      />
      <AppSelect
        v-model="city"
        :options="cityOptions"
        label="Город"
        placeholder="Любой"
        hint="Подойдут и те, кто готов к переезду. Чтобы увидеть удалённых кандидатов из других городов, выберите формат «Удалённо»."
      />
    </section>

    <section class="panel__group">
      <h3 class="section-title">Навыки</h3>
      <SkillPicker
        :model-value="filters.skills_required"
        label="Обязательные"
        :exclude="filters.skills_optional"
        @update:model-value="emit('update', { skills_required: $event })"
      />
      <SkillPicker
        :model-value="filters.skills_optional"
        label="Желательные"
        :exclude="filters.skills_required"
        @update:model-value="emit('update', { skills_optional: $event })"
      />
      <AppCheckbox
        :model-value="filters.strict_skills"
        label="Все обязательные навыки строго"
        hint="Оставить тех, у кого каждый обязательный навык подтверждён хотя бы на минимальном уровне."
        @update:model-value="emit('update', { strict_skills: $event })"
      />
    </section>

    <section class="panel__group">
      <h3 class="section-title">Подтверждение</h3>
      <AppCheckbox
        :model-value="filters.fsp_verified_only"
        label="Только с результатами ФСП"
        hint="Есть хотя бы одно достижение из реестра."
        @update:model-value="emit('update', { fsp_verified_only: $event })"
      />
      <AppCheckbox
        :model-value="filters.confirmed_only"
        label="Только с подтверждением"
        hint="Хотя бы один факт подтверждён ФСП или тестом платформы."
        @update:model-value="emit('update', { confirmed_only: $event })"
      />
      <ChipSelect
        :model-value="filters.disciplines"
        :options="reference.disciplineOptions"
        label="Дисциплины ФСП"
        hint="Нужен результат хотя бы в одной из выбранных."
        @update:model-value="emit('update', { disciplines: $event })"
      />
    </section>

    <section class="panel__group">
      <h3 class="section-title">Бюджет</h3>
      <AppInput
        v-model="salaryMax"
        type="number"
        label="Не больше"
        placeholder="Например, 180000"
        suffix="₽"
        :min="0"
        :step="5000"
        inputmode="numeric"
        hint="Кандидаты, которые не назвали ожидания, остаются в выдаче."
      />
    </section>
  </div>
</template>

<style scoped>
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
}
.panel__group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
</style>
