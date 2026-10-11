<script setup lang="ts">
import { computed, ref } from 'vue'

import { fieldErrors } from '@/api/client'
import { createVacancy, listVacancies, updateVacancy } from '@/api/employer'
import type { Vacancy, VacancyInput } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppModal from '@/components/AppModal.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import MoneyRange from '@/components/MoneyRange.vue'
import PageHeader from '@/components/PageHeader.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import SkillChip from '@/components/SkillChip.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { formatDate } from '@/utils/format'

import VacancyForm from './components/VacancyForm.vue'
import { searchLocation } from './searchFilters'

// Own vacancies: a list with the salary range and the number of offers, create / edit in a modal form,
// "Подобрать кандидатов" (search for this vacancy) and "В архив".

type View = 'active' | 'archive'

const DESCRIPTION_PREVIEW = 220

const reference = useReferenceStore()
const toast = useToastStore()

const { data: vacancies, status, errorMessage, load, setData } = useLoader(() => listVacancies())

const view = ref<View>('active')
const list = computed(() => vacancies.value ?? [])
const activeList = computed(() => list.value.filter((vacancy) => vacancy.is_active))
const archivedList = computed(() => list.value.filter((vacancy) => !vacancy.is_active))
const shown = computed(() => (view.value === 'active' ? activeList.value : archivedList.value))

const viewOptions = computed(() => [
  { value: 'active' as const, label: `Активные · ${activeList.value.length}` },
  { value: 'archive' as const, label: `В архиве · ${archivedList.value.length}` },
])

function replaceVacancy(updated: Vacancy): void {
  setData(list.value.map((vacancy) => (vacancy.id === updated.id ? updated : vacancy)))
}

// ---------- Create / edit ----------

const formOpen = ref(false)
const editing = ref<Vacancy | null>(null)
const saving = ref(false)
const serverErrors = ref<Record<string, string>>({})
/** Changes with every opening, so that the form starts from a clean state. */
const formKey = ref(0)

function openCreate(): void {
  editing.value = null
  serverErrors.value = {}
  formKey.value += 1
  formOpen.value = true
}

function openEdit(vacancy: Vacancy): void {
  editing.value = vacancy
  serverErrors.value = {}
  formKey.value += 1
  formOpen.value = true
}

async function save(input: VacancyInput): Promise<void> {
  saving.value = true
  serverErrors.value = {}
  try {
    if (editing.value === null) {
      const created = await createVacancy(input)
      setData([created, ...list.value])
      view.value = 'active'
      toast.success('Вакансия создана. Теперь можно подобрать под неё кандидатов.')
    } else {
      replaceVacancy(await updateVacancy(editing.value.id, input))
      toast.success('Изменения сохранены.')
    }
    formOpen.value = false
  } catch (err) {
    serverErrors.value = fieldErrors(err)
    toast.fromError(err)
  } finally {
    saving.value = false
  }
}

// ---------- Archive / restore ----------

const archiveTarget = ref<Vacancy | null>(null)
const archiveOpen = ref(false)
const archiving = ref(false)
const restoringId = ref<number | null>(null)

function askArchive(vacancy: Vacancy): void {
  archiveTarget.value = vacancy
  archiveOpen.value = true
}

async function archive(): Promise<void> {
  const target = archiveTarget.value
  if (target === null) {
    return
  }
  archiving.value = true
  try {
    replaceVacancy(await updateVacancy(target.id, { is_active: false }))
    archiveOpen.value = false
    toast.success('Вакансия в архиве.')
  } catch (err) {
    toast.fromError(err)
  } finally {
    archiving.value = false
  }
}

async function restore(vacancy: Vacancy): Promise<void> {
  restoringId.value = vacancy.id
  try {
    replaceVacancy(await updateVacancy(vacancy.id, { is_active: true }))
    toast.success('Вакансия снова активна.')
  } catch (err) {
    toast.fromError(err)
  } finally {
    restoringId.value = null
  }
}

// ---------- Presentation ----------

const expanded = ref<ReadonlySet<number>>(new Set())

function toggleExpanded(id: number): void {
  const next = new Set(expanded.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expanded.value = next
}

function categoryLine(vacancy: Vacancy): string {
  const parts = [reference.stackTitle(vacancy.stack), reference.gradeTitle(vacancy.grade)]
  if (vacancy.team_role !== null) {
    parts.push(reference.teamRoleTitle(vacancy.team_role))
  }
  return parts.join(' · ')
}

function conditionsLine(vacancy: Vacancy): string {
  const parts: string[] = []
  parts.push(
    vacancy.work_formats.length > 0
      ? reference.joinTitles(vacancy.work_formats, reference.workFormatTitle)
      : 'формат не важен',
  )
  parts.push(vacancy.city ?? 'город не важен')
  return parts.join(' · ')
}
</script>

<template>
  <PageHeader
    title="Вакансии"
    eyebrow="Работодатель"
    subtitle="Оффер всегда уходит по вакансии: кандидат видит, куда его зовут и за какие деньги. Вакансию можно использовать и как готовый запрос: платформа сама подберёт под неё людей."
  >
    <template #actions>
      <AppButton @click="openCreate">
        <AppIcon name="plus" :size="18" />
        Новая вакансия
      </AppButton>
    </template>
  </PageHeader>

  <StateBlock v-if="status === 'loading' || status === 'idle'" state="loading" title="Загружаем вакансии…" />
  <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />

  <StateBlock
    v-else-if="list.length === 0"
    state="empty"
    title="Вакансий пока нет"
    text="Создайте первую: укажите стек, грейд, навыки и вилку. По ней платформа подберёт кандидатов, а вы сможете отправить им оффер."
  >
    <template #action>
      <AppButton @click="openCreate">
        <AppIcon name="plus" :size="18" />
        Создать вакансию
      </AppButton>
    </template>
  </StateBlock>

  <template v-else>
    <SegmentedControl v-model="view" :options="viewOptions" label="Показать" />

    <StateBlock
      v-if="shown.length === 0"
      state="empty"
      :title="view === 'active' ? 'Активных вакансий нет' : 'В архиве пусто'"
      :text="
        view === 'active'
          ? 'Все вакансии в архиве. Верните одну из них в работу или создайте новую.'
          : 'Сюда попадают вакансии, которые вы убрали из работы. Отправленные по ним офферы остаются у кандидатов.'
      "
    />

    <div v-else class="vac-list">
      <article v-for="vacancy in shown" :key="vacancy.id" class="vac card" :class="{ 'is-archived': !vacancy.is_active }">
        <header class="vac__head">
          <div class="vac__title-block">
            <h2 class="vac__title">{{ vacancy.title }}</h2>
            <p class="vac__category">{{ categoryLine(vacancy) }}</p>
          </div>
          <span class="vac__status" :class="vacancy.is_active ? 'is-active' : 'is-archived'">
            {{ vacancy.is_active ? 'Активна' : 'В архиве' }}
          </span>
        </header>

        <MoneyRange :from="vacancy.salary_from" :to="vacancy.salary_to" size="lg" empty-text="Вилка не указана" />

        <div v-if="vacancy.description" class="vac__desc">
          <p class="vac__text" :class="{ 'is-clamped': vacancy.description.length > DESCRIPTION_PREVIEW && !expanded.has(vacancy.id) }">
            {{ vacancy.description }}
          </p>
          <button
            v-if="vacancy.description.length > DESCRIPTION_PREVIEW"
            type="button"
            class="vac__more"
            :aria-expanded="expanded.has(vacancy.id)"
            @click="toggleExpanded(vacancy.id)"
          >
            {{ expanded.has(vacancy.id) ? 'Свернуть' : 'Показать полностью' }}
          </button>
        </div>

        <div v-if="vacancy.skills_required.length > 0 || vacancy.skills_optional.length > 0" class="vac__skills">
          <div v-if="vacancy.skills_required.length > 0" class="vac__skill-group">
            <p class="vac__label">Обязательные</p>
            <div class="vac__chips">
              <SkillChip v-for="skill in vacancy.skills_required" :key="skill" :title="reference.skillTitle(skill)" />
            </div>
          </div>
          <div v-if="vacancy.skills_optional.length > 0" class="vac__skill-group">
            <p class="vac__label">Желательные</p>
            <div class="vac__chips">
              <SkillChip v-for="skill in vacancy.skills_optional" :key="skill" :title="reference.skillTitle(skill)" />
            </div>
          </div>
        </div>

        <p class="vac__conditions">{{ conditionsLine(vacancy) }}</p>

        <footer class="vac__foot">
          <p class="vac__stats">
            <span>Офферов: <strong class="num">{{ vacancy.offers_count }}</strong></span>
            <span class="muted">создана {{ formatDate(vacancy.created_at) }}</span>
          </p>
          <div class="vac__actions">
            <AppButton v-if="vacancy.is_active" size="sm" :to="searchLocation({ vacancy_id: vacancy.id })">
              <AppIcon name="search" :size="16" />
              Подобрать кандидатов
            </AppButton>
            <AppButton variant="secondary" size="sm" @click="openEdit(vacancy)">Редактировать</AppButton>
            <AppButton v-if="vacancy.is_active" variant="ghost" size="sm" @click="askArchive(vacancy)">В архив</AppButton>
            <AppButton
              v-else
              variant="ghost"
              size="sm"
              :loading="restoringId === vacancy.id"
              @click="restore(vacancy)"
            >
              Вернуть в работу
            </AppButton>
          </div>
        </footer>
      </article>
    </div>
  </template>

  <AppModal v-model="formOpen" :title="editing ? 'Редактировать вакансию' : 'Новая вакансия'" size="lg" :closable="!saving">
    <VacancyForm :key="formKey" :vacancy="editing" :server-errors="serverErrors" @submit="save" />
    <template #footer>
      <AppButton variant="ghost" :disabled="saving" @click="formOpen = false">Отмена</AppButton>
      <AppButton type="submit" form="vacancy-form" :loading="saving">
        {{ editing ? 'Сохранить' : 'Создать вакансию' }}
      </AppButton>
    </template>
  </AppModal>

  <ConfirmModal
    v-model="archiveOpen"
    title="Убрать вакансию в архив?"
    :message="`«${archiveTarget?.title ?? ''}» перестанет участвовать в подборе, и новые офферы по ней отправить будет нельзя. Уже отправленные офферы останутся у кандидатов. Вакансию можно вернуть в работу.`"
    confirm-label="В архив"
    :loading="archiving"
    @confirm="archive"
  />
</template>

<style scoped>
.vac-list {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-4);
}
.vac {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
}
.vac.is-archived {
  background: var(--c-surface-2);
}
.vac.is-archived .vac__title,
.vac.is-archived :deep(.money) {
  color: var(--c-text-muted);
}
.vac__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
}
.vac__title-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.vac__title {
  font-size: var(--fs-lg);
  overflow-wrap: anywhere;
}
.vac__category {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--c-text-muted);
}
.vac__status {
  flex: none;
  padding: 3px 10px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 600;
  white-space: nowrap;
}
.vac__status.is-active {
  border-color: var(--c-success-border);
  background: var(--c-success-soft);
  color: var(--c-success-text);
}
.vac__status.is-archived {
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
}
.vac__desc {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.vac__text {
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--c-text);
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.vac__text.is-clamped {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.vac__more {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--c-primary);
  font-size: var(--fs-sm);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.vac__skills {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.vac__skill-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.vac__label {
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.vac__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.vac__conditions {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.vac__foot {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin-top: auto;
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
}
.vac__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 2px var(--sp-4);
  font-size: var(--fs-sm);
}
.vac__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}

@media (min-width: 900px) {
  .vac-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
