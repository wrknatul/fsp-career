<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import type { Grade, Stack, TeamRole, Vacancy, VacancyInput, WorkFormat } from '@/api/types'
import AppInput from '@/components/AppInput.vue'
import AppSelect from '@/components/AppSelect.vue'
import AppTextarea from '@/components/AppTextarea.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import SkillPicker from '@/components/SkillPicker.vue'
import { useReferenceStore } from '@/stores/reference'

// Create / edit form of a vacancy. The form has the id "vacancy-form", so that a submit button in the modal
// footer can reach it: <AppButton type="submit" form="vacancy-form">. The page sends the request.
//   <VacancyForm :vacancy="editing" :server-errors="fieldErrors" @submit="save" />
const props = defineProps<{
  /** null - a new vacancy. */
  vacancy: Vacancy | null
  /** Field -> message from the server (VALIDATION_ERROR). */
  serverErrors?: Record<string, string>
}>()

const emit = defineEmits<{ submit: [input: VacancyInput] }>()

const MAX_SALARY = 100_000_000
const MAX_DESCRIPTION = 5000

const reference = useReferenceStore()

const title = ref(props.vacancy?.title ?? '')
const description = ref(props.vacancy?.description ?? '')
const stack = ref<Stack | null>(props.vacancy?.stack ?? null)
const grade = ref<Grade | null>(props.vacancy?.grade ?? null)
const teamRole = ref<TeamRole | null>(props.vacancy?.team_role ?? null)
const skillsRequired = ref<string[]>([...(props.vacancy?.skills_required ?? [])])
const skillsOptional = ref<string[]>([...(props.vacancy?.skills_optional ?? [])])
const workFormats = ref<WorkFormat[]>([...(props.vacancy?.work_formats ?? [])])
const city = ref<string | null>(props.vacancy?.city ?? null)
const salaryFrom = ref<number | null>(props.vacancy?.salary_from ?? null)
const salaryTo = ref<number | null>(props.vacancy?.salary_to ?? null)

const errors = ref<Record<string, string>>({})

function errorOf(key: string): string {
  return errors.value[key] ?? props.serverErrors?.[key] ?? ''
}

// A city of an old vacancy may be missing from the dictionary: keep it selectable.
const cityOptions = computed(() => {
  const options = [...reference.cityOptions]
  if (city.value !== null && !options.some((option) => option.value === city.value)) {
    options.unshift({ value: city.value, label: city.value })
  }
  return options
})

// Fallback when the server did not send the list of cities: a plain text field.
const cityText = computed<string>({
  get: () => city.value ?? '',
  set: (value) => {
    city.value = value === '' ? null : value
  },
})

function checkSalary(value: number | null): boolean {
  return value === null || (Number.isInteger(value) && value > 0 && value <= MAX_SALARY)
}

function validate(): boolean {
  const next: Record<string, string> = {}
  if (title.value.trim().length < 2) {
    next.title = 'Назовите вакансию: хотя бы два символа'
  } else if (title.value.trim().length > 200) {
    next.title = 'Название длиннее 200 символов'
  }
  if (description.value.length > MAX_DESCRIPTION) {
    next.description = 'Описание длиннее 5000 символов'
  }
  if (stack.value === null) {
    next.stack = 'Выберите стек'
  }
  if (grade.value === null) {
    next.grade = 'Выберите грейд'
  }
  if (!checkSalary(salaryFrom.value)) {
    next.salary_from = 'Сумма — целое число рублей больше нуля'
  }
  if (!checkSalary(salaryTo.value)) {
    next.salary_to = 'Сумма — целое число рублей больше нуля'
  }
  if (next.salary_from === undefined && next.salary_to === undefined && salaryFrom.value !== null && salaryTo.value !== null && salaryFrom.value > salaryTo.value) {
    next.salary_to = 'Верхняя граница не может быть ниже нижней'
  }
  errors.value = next
  return Object.keys(next).length === 0
}

const formRef = ref<HTMLFormElement | null>(null)

/** Put the cursor into the first field with a mistake, so that a keyboard user lands on it. */
async function focusFirstError(): Promise<void> {
  await nextTick()
  formRef.value?.querySelector<HTMLElement>('.field--error .field__control')?.focus()
}

function onSubmit(): void {
  if (!validate() || stack.value === null || grade.value === null) {
    void focusFirstError()
    return
  }
  const cityValue = city.value === null ? '' : city.value.trim()
  emit('submit', {
    title: title.value.trim(),
    description: description.value.trim(),
    stack: stack.value,
    grade: grade.value,
    team_role: teamRole.value,
    skills_required: skillsRequired.value,
    skills_optional: skillsOptional.value,
    work_formats: workFormats.value,
    city: cityValue === '' ? null : cityValue,
    salary_from: salaryFrom.value,
    salary_to: salaryTo.value,
    is_active: props.vacancy?.is_active ?? true,
  })
}
</script>

<template>
  <form id="vacancy-form" ref="formRef" class="vform" novalidate @submit.prevent="onSubmit">
    <AppInput
      v-model="title"
      label="Название"
      placeholder="Например, Python-разработчик"
      required
      :maxlength="200"
      :error="errorOf('title')"
    />

    <AppTextarea
      v-model="description"
      label="Описание"
      placeholder="Задачи, команда, чем предстоит заниматься"
      :rows="5"
      :maxlength="MAX_DESCRIPTION"
      hint="Текст вакансии участвует в подборе: по нему считается совпадение с профилями кандидатов."
      :error="errorOf('description')"
    />

    <div class="vform__grid">
      <AppSelect
        v-model="stack"
        :options="reference.stackOptions"
        label="Стек"
        placeholder="Выберите стек"
        required
        :error="errorOf('stack')"
      />
      <AppSelect
        v-model="grade"
        :options="reference.gradeOptions"
        label="Грейд"
        placeholder="Выберите грейд"
        required
        :error="errorOf('grade')"
      />
      <AppSelect
        v-model="teamRole"
        :options="reference.teamRoleOptions"
        label="Роль в команде"
        placeholder="Не важна"
        :error="errorOf('team_role')"
      />
    </div>

    <SkillPicker
      v-model="skillsRequired"
      label="Обязательные навыки"
      :exclude="skillsOptional"
      hint="Без них кандидат не подойдёт. Чем строже список, тем короче выдача."
      :error="errorOf('skills_required')"
    />
    <SkillPicker
      v-model="skillsOptional"
      label="Желательные навыки"
      :exclude="skillsRequired"
      hint="Будут плюсом: поднимают кандидата в выдаче, но не отсекают."
      :error="errorOf('skills_optional')"
    />

    <ChipSelect
      v-model="workFormats"
      :options="reference.workFormatOptions"
      label="Формат работы"
      hint="Ничего не выбрано — формат не важен."
      :error="errorOf('work_formats')"
    />

    <div class="vform__grid vform__grid--two">
      <AppSelect
        v-if="cityOptions.length > 0"
        v-model="city"
        :options="cityOptions"
        label="Город"
        placeholder="Не важен"
        :error="errorOf('city')"
      />
      <AppInput v-else v-model="cityText" label="Город" placeholder="Например, Казань" :maxlength="100" :error="errorOf('city')" />
    </div>

    <fieldset class="vform__salary">
      <legend class="field__label">Зарплатная вилка, ₽ в месяц</legend>
      <div class="vform__grid vform__grid--two">
        <AppInput
          v-model="salaryFrom"
          type="number"
          label="От"
          suffix="₽"
          :min="1"
          :step="5000"
          inputmode="numeric"
          :error="errorOf('salary_from')"
        />
        <AppInput
          v-model="salaryTo"
          type="number"
          label="До"
          suffix="₽"
          :min="1"
          :step="5000"
          inputmode="numeric"
          :error="errorOf('salary_to')"
        />
      </div>
      <p class="field__hint">Вилку видит только кандидат, которому вы отправите оффер. Можно указать одну границу.</p>
    </fieldset>
  </form>
</template>

<style scoped>
.vform {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}
.vform__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
}
.vform__salary {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.vform__salary legend {
  padding: 0;
  margin-bottom: var(--sp-2);
}
@media (min-width: 560px) {
  .vform__grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .vform__grid--two {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
