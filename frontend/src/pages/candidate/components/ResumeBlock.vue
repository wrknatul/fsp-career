<script setup lang="ts">
import { computed, ref } from 'vue'

import { deleteResume, getDemoResume, uploadResume } from '@/api/candidate'
import type { CandidateProfile, Category, ResumeParseResult } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppTextarea from '@/components/AppTextarea.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { formatDate, formatMoney, formatNumber, formatYears } from '@/utils/format'

import CategoryChange from './CategoryChange.vue'

// Resume: paste text, upload .txt/.pdf or insert the demo sample; shows what the parser found.
const props = defineProps<{ profile: CandidateProfile }>()
const emit = defineEmits<{ updated: [profile: CandidateProfile] }>()

const reference = useReferenceStore()
const toast = useToastStore()

const MAX_FILE_BYTES = 2 * 1024 * 1024
const MAX_TEXT_CHARS = 100_000

const text = ref('')
const busy = ref(false)
const loadingDemo = ref(false)
const result = ref<ResumeParseResult | null>(null)
const before = ref<Category | null>(null)
const askDelete = ref(false)
const deleting = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const inputError = ref('')

const PREF_TITLES: Record<string, string> = {
  city: 'город',
  work_formats: 'формат работы',
  salary_expectation: 'зарплатные ожидания',
  relocation: 'готовность к переезду',
}

const appliedText = computed(() => {
  if (result.value === null) {
    return ''
  }
  const prefs = result.value.applied_prefs
  if (prefs.length === 0) {
    return 'Анкета уже заполнена, ничего не перезаписано.'
  }
  return `В анкету подставлено: ${prefs.map((pref) => PREF_TITLES[pref] ?? pref).join(', ')}.`
})

const extractedFacts = computed(() => {
  if (result.value === null) {
    return []
  }
  const extracted = result.value.extracted
  const rows: { label: string; value: string }[] = []
  rows.push({
    label: 'Опыт в ИТ',
    value: extracted.experience_years > 0 ? formatYears(extracted.experience_years) : 'не найден',
  })
  if (extracted.work_formats.length > 0) {
    rows.push({ label: 'Формат работы', value: reference.joinTitles(extracted.work_formats, reference.workFormatTitle) })
  }
  if (extracted.city !== null) {
    rows.push({ label: 'Город', value: extracted.city })
  }
  if (extracted.salary_expectation !== null) {
    rows.push({ label: 'Ожидания', value: formatMoney(extracted.salary_expectation) })
  }
  if (extracted.is_lead) {
    rows.push({ label: 'Руководство', value: 'есть должность тимлида' })
  }
  return rows
})

async function parse(input: { text: string } | { file: File }): Promise<void> {
  if (busy.value) {
    return
  }
  busy.value = true
  inputError.value = ''
  const categoryBefore = props.profile.category
  try {
    const parsed = await uploadResume(input)
    before.value = categoryBefore
    result.value = parsed
    emit('updated', parsed.profile)
    if ('file' in input) {
      text.value = ''
    }
    toast.success('Резюме разобрано, профиль обновлён')
  } catch (err) {
    toast.fromError(err)
  } finally {
    busy.value = false
  }
}

function submitText(): void {
  const value = text.value.trim()
  if (value === '') {
    inputError.value = 'Вставьте текст резюме, загрузите файл или подставьте пример.'
    return
  }
  void parse({ text: value })
}

function pickFile(): void {
  fileInput.value?.click()
}

function onFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file === undefined) {
    return
  }
  const name = file.name.toLowerCase()
  if (!name.endsWith('.txt') && !name.endsWith('.pdf')) {
    inputError.value = 'Подходят только файлы .txt и .pdf.'
    return
  }
  if (file.size > MAX_FILE_BYTES) {
    inputError.value = 'Файл больше 2 МБ. Сохраните резюме короче или вставьте текст.'
    return
  }
  void parse({ file })
}

async function fillDemo(): Promise<void> {
  if (loadingDemo.value) {
    return
  }
  loadingDemo.value = true
  inputError.value = ''
  try {
    const demo = await getDemoResume()
    text.value = demo.text
  } catch (err) {
    toast.fromError(err)
  } finally {
    loadingDemo.value = false
  }
}

async function remove(): Promise<void> {
  if (deleting.value) {
    return
  }
  deleting.value = true
  try {
    const next = await deleteResume()
    result.value = null
    before.value = null
    emit('updated', next)
    askDelete.value = false
    toast.info('Резюме удалено, грейд пересчитан')
  } catch (err) {
    toast.fromError(err)
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <section id="resume" class="rs card" aria-labelledby="rs-title">
    <header class="rs__head">
      <h2 id="rs-title" class="h3">Резюме</h2>
      <p class="rs__sub">
        Навыки и опыт из резюме помечаются «Из резюме»: это не подтверждение, но именно опыт определяет грейд.
      </p>
    </header>

    <div v-if="profile.resume" class="rs__current">
      <span class="rs__current-icon" aria-hidden="true"><AppIcon name="check" :size="16" /></span>
      <div class="rs__current-text">
        <p class="rs__current-title">Резюме разобрано</p>
        <p class="rs__current-meta">
          {{ profile.resume.filename ?? 'Вставленный текст' }} · {{ formatDate(profile.resume.parsed_at) }} ·
          <span class="num">{{ formatNumber(profile.resume.chars) }}</span> симв.
        </p>
      </div>
      <AppButton variant="danger" size="sm" @click="askDelete = true">Удалить</AppButton>
    </div>

    <div class="rs__input">
      <AppTextarea
        v-model="text"
        :label="profile.resume ? 'Заменить резюме' : 'Текст резюме'"
        :rows="8"
        :maxlength="MAX_TEXT_CHARS"
        placeholder="Вставьте текст резюме: должности с датами, стек, город, формат работы…"
        :error="inputError"
        :disabled="busy"
        hint="Новое резюме заменит все факты «Из резюме». Контакты из текста в профиль не попадают."
      />
      <div class="rs__actions">
        <AppButton :loading="busy" :disabled="text.trim() === ''" @click="submitText">Разобрать</AppButton>
        <AppButton variant="secondary" :loading="loadingDemo" :disabled="busy" @click="fillDemo">
          Подставить пример
        </AppButton>
        <AppButton variant="secondary" :disabled="busy" @click="pickFile">
          <AppIcon name="plus" :size="16" />Загрузить .txt или .pdf
        </AppButton>
        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          accept=".txt,.pdf,text/plain,application/pdf"
          tabindex="-1"
          aria-label="Файл резюме"
          @change="onFile"
        />
      </div>
      <p class="rs__privacy">
        <AppIcon name="shield" :size="14" />
        <span>
          Файл до 2 МБ, PDF до 20 страниц. Разбор идёт по правилам на нашем сервере: резюме не уходит во внешние сервисы.
        </span>
      </p>
    </div>

    <div v-if="result" class="rs__result" aria-live="polite">
      <h3 class="section-title">Что нашли в резюме</h3>

      <dl class="rs__facts">
        <div v-for="row in extractedFacts" :key="row.label" class="rs__fact">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.value }}</dd>
        </div>
      </dl>

      <div v-if="result.extracted.skills.length > 0" class="rs__block">
        <p class="rs__block-title">Навыки <SourceBadge verification="parsed" size="sm" /></p>
        <ul class="rs__skills">
          <li v-for="skill in result.extracted.skills" :key="skill.skill" class="rs__skill">
            <span>{{ skill.title }}</span>
            <span class="rs__skill-level num" :title="`Уровень ${skill.level} из 3: из резюме выше второго не бывает`">
              ур. {{ skill.level }}
            </span>
          </li>
        </ul>
      </div>
      <p v-else class="rs__none">Навыков из справочника в тексте не нашлось. Проверьте, что в резюме названы технологии.</p>

      <div v-if="result.extracted.positions.length > 0" class="rs__block">
        <p class="rs__block-title">Опыт по позициям</p>
        <ul class="rs__positions">
          <li v-for="(position, index) in result.extracted.positions" :key="index" class="rs__position">
            <div class="rs__position-main">
              <p class="rs__position-title">{{ position.title }}</p>
              <p class="rs__position-meta">
                <template v-if="position.company">{{ position.company }} · </template>{{ position.period }}
                <template v-if="position.years > 0"> · {{ formatYears(position.years) }}</template>
              </p>
            </div>
            <span class="rs__tag" :class="position.is_it ? 'is-it' : 'is-other'">
              {{ position.is_it ? 'Засчитан как ИТ-опыт' : 'Не засчитан: не ИТ' }}
            </span>
          </li>
        </ul>
      </div>

      <p class="rs__applied"><AppIcon name="info" :size="16" /><span>{{ appliedText }}</span></p>

      <CategoryChange v-if="before" :before="before" :after="result.profile.category" title="Что изменилось в категории" />
    </div>

    <ConfirmModal
      v-model="askDelete"
      title="Удалить резюме?"
      message="Навыки и опыт «Из резюме» пропадут из профиля, грейд пересчитается. Поля анкеты, которые заполнились из резюме, останутся."
      confirm-label="Удалить"
      danger
      :loading="deleting"
      @confirm="remove"
    />
  </section>
</template>

<style scoped>
.rs {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  scroll-margin-top: 80px;
}
.rs__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.rs__sub {
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-text-muted);
}
.rs__current {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3) var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--c-success-border);
  border-radius: var(--r-md);
  background: var(--c-success-soft);
}
.rs__current-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--c-success);
  color: #fff;
}
.rs__current-text {
  flex: 1 1 200px;
  min-width: 0;
}
.rs__current-title {
  font-weight: 600;
  color: var(--c-success-text);
}
.rs__current-meta {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
  overflow-wrap: anywhere;
}
.rs__input {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.rs__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}
.rs__privacy {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: var(--fs-xs);
  line-height: 1.5;
  color: var(--c-text-muted);
}
.rs__privacy :deep(svg) {
  margin-top: 2px;
}
.rs__result {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding-top: var(--sp-5);
  border-top: 1px solid var(--c-border);
}
.rs__facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--sp-3) var(--sp-5);
  margin: 0;
}
.rs__fact {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rs__fact dt {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.rs__fact dd {
  margin: 0;
  font-weight: 600;
  color: var(--c-ink);
}
.rs__block {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.rs__block-title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-text-muted);
}
.rs__skills {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.rs__skill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px 4px 12px;
  border: 1px solid var(--c-border-strong);
  border-radius: var(--r-pill);
  background: var(--c-surface);
  font-size: var(--fs-sm);
  font-weight: 500;
}
.rs__skill-level {
  padding: 1px 8px;
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
  font-size: var(--fs-xs);
  font-weight: 600;
}
.rs__none {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.rs__positions {
  list-style: none;
  display: flex;
  flex-direction: column;
}
.rs__position {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-2) var(--sp-4);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--c-border);
}
.rs__position:last-child {
  border-bottom: 0;
}
.rs__position-main {
  flex: 1 1 220px;
  min-width: 0;
}
.rs__position-title {
  font-weight: 600;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.rs__position-meta {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.rs__tag {
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 600;
  white-space: nowrap;
}
.rs__tag.is-it {
  background: var(--c-success-soft);
  color: var(--c-success-text);
}
.rs__tag.is-other {
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
}
.rs__applied {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: var(--fs-sm);
  line-height: 1.5;
}
.rs__applied :deep(svg) {
  margin-top: 2px;
  color: var(--c-primary);
}
</style>
