<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { hasErrorCode } from '@/api/client'
import { getCandidate, listVacancies } from '@/api/employer'
import type { CandidateCard as CandidateCardData, Verification } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import CategoryCard from '@/components/CategoryCard.vue'
import ConfidenceMeter from '@/components/ConfidenceMeter.vue'
import FactList from '@/components/FactList.vue'
import GradeExplanation from '@/components/GradeExplanation.vue'
import MoneyRange from '@/components/MoneyRange.vue'
import PageHeader from '@/components/PageHeader.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { formatCount, formatDate } from '@/utils/format'

import ContactLines from './components/ContactLines.vue'
import FspTimeline from './components/FspTimeline.vue'
import OfferForm from './components/OfferForm.vue'
import OfferStatusBadge from './components/OfferStatusBadge.vue'
import { isHiddenEvidence } from './redaction'

// Card of one candidate. Above all it answers two questions: what is the category based on, and what
// exactly confirms it. Contacts and the full name stay closed until the candidate accepts an offer.

const route = useRoute()
const router = useRouter()
const reference = useReferenceStore()
const toast = useToastStore()

const rawId = Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
const candidateId = Number(rawId)

function positiveInt(raw: unknown): number | null {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value !== 'string' || !/^\d{1,10}$/.test(value)) {
    return null
  }
  const parsed = Number(value)
  return parsed > 0 ? parsed : null
}

/** The vacancy the search was run for: offered first in the offer form. */
const presetVacancyId = positiveInt(route.query.vacancy_id)

const { data: card, status, errorMessage, load, setData } = useLoader(() => getCandidate(candidateId))
const {
  data: vacancies,
  status: vacanciesStatus,
  errorMessage: vacanciesError,
  load: loadVacancies,
} = useLoader(() => listVacancies())

async function reloadCard(): Promise<void> {
  try {
    setData(await getCandidate(candidateId))
  } catch (err) {
    if (hasErrorCode(err, 'NOT_FOUND')) {
      // The candidate hid the profile meanwhile: drop the card with its offer form and show the page error
      // state (one message, no second toast; the form already toasted the failed send).
      card.value = null
      await load()
      return
    }
    toast.fromError(err)
  }
}

async function onOfferSent(): Promise<void> {
  await reloadCard()
  await loadVacancies()
}

async function onStale(): Promise<void> {
  await Promise.all([reloadCard(), loadVacancies()])
}

// ---------- Navigation ----------

function goBack(): void {
  const back: unknown = router.options.history.state.back
  if (typeof back === 'string' && back.startsWith('/employer')) {
    router.back()
  } else {
    void router.push({ name: 'employer-search' })
  }
}

function scrollToOffer(): void {
  document.getElementById('offer')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// A link from a search result "Отправить оффер" opens the card already at the form.
let scrolledToOffer = false
watch(
  card,
  async (value) => {
    if (value === null || scrolledToOffer || route.query.offer !== '1') {
      return
    }
    scrolledToOffer = true
    await nextTick()
    scrollToOffer()
  },
  { immediate: true },
)

// ---------- What is shown ----------

const subtitle = computed(() => {
  const data = card.value
  if (data === null) {
    return ''
  }
  const parts: string[] = []
  if (data.city) parts.push(data.city)
  if (data.relocation) parts.push('готов к переезду')
  return parts.join(' · ')
})

const fspResults = computed(() =>
  (card.value?.facts ?? []).filter((fact) => fact.kind === 'achievement' && fact.source === 'fsp'),
)
// Until an offer is accepted the backend swaps whole evidence links for "[скрыто]": drop that placeholder
// instead of showing it as a quote (the note under "Факты профиля" explains why the links are missing).
const otherFacts = computed(() =>
  (card.value?.facts ?? [])
    .filter((fact) => !(fact.kind === 'achievement' && fact.source === 'fsp'))
    .map((fact) => (isHiddenEvidence(fact.evidence) ? { ...fact, evidence: null } : fact)),
)
const hasHiddenLinks = computed(() => (card.value?.facts ?? []).some((fact) => isHiddenEvidence(fact.evidence)))

type SourceStat = { key: Verification; count: number; text: string }

const RESULTS = ['результат', 'результата', 'результатов'] as const
const TESTS = ['тест', 'теста', 'тестов'] as const
const FACTS = ['факт', 'факта', 'фактов'] as const
const ACHIEVEMENTS = ['достижение', 'достижения', 'достижений'] as const

/** "Чем подтверждён профиль" at a glance: how many facts come from each source. */
const sourceStats = computed<SourceStat[]>(() => {
  const facts = card.value?.facts ?? []
  const tests = facts.filter((fact) => fact.kind === 'skill' && fact.source === 'test').length
  const resume = facts.filter((fact) => fact.source === 'resume').length
  const declared = facts.filter((fact) => fact.source === 'self').length
  const fsp = fspResults.value.length
  // The badge in front already names the source, so the text stays short: it has to fit one line on a phone.
  return [
    { key: 'verified', count: fsp, text: fsp > 0 ? formatCount(fsp, RESULTS) : 'результатов нет' },
    { key: 'tested', count: tests, text: tests > 0 ? formatCount(tests, TESTS) : 'тестов нет' },
    { key: 'parsed', count: resume, text: resume > 0 ? formatCount(resume, FACTS) : 'резюме нет' },
    { key: 'declared', count: declared, text: declared > 0 ? formatCount(declared, ACHIEVEMENTS) : 'нет' },
  ]
})

type ContactState = 'open' | 'pending' | 'declined' | 'closed'

const contactState = computed<ContactState>(() => {
  const data = card.value
  if (data === null) {
    return 'closed'
  }
  if (data.contacts !== null) {
    return 'open'
  }
  if (data.offers.some((offer) => offer.status === 'sent')) {
    return 'pending'
  }
  if (data.offers.length > 0 && data.offers.every((offer) => offer.status === 'declined')) {
    return 'declined'
  }
  return 'closed'
})

const contactNote = computed(() => {
  switch (contactState.value) {
    case 'pending':
      return 'Оффер отправлен, ждём ответа кандидата.'
    case 'declined':
      return 'Кандидат отклонил оффер, контакты остаются скрытыми. Можно предложить другую вакансию.'
    default:
      return ''
  }
})

function formatList(data: CandidateCardData): string {
  return data.work_formats.length > 0 ? reference.joinTitles(data.work_formats, reference.workFormatTitle) : 'не указан'
}
</script>

<template>
  <PageHeader :title="card?.display_name ?? 'Карточка кандидата'" eyebrow="Кандидат" :subtitle="subtitle">
    <template #actions>
      <AppButton variant="secondary" @click="goBack">
        <AppIcon class="flip" name="arrow-right" :size="18" />
        К результатам
      </AppButton>
      <AppButton v-if="card" @click="scrollToOffer">Отправить оффер</AppButton>
    </template>
  </PageHeader>

  <StateBlock v-if="card === null && status !== 'error'" state="loading" title="Открываем карточку…" />

  <StateBlock v-else-if="card === null" state="error" :text="errorMessage" @retry="load" />

  <template v-else>
    <ul class="sources" aria-label="Чем подтверждён профиль">
      <li v-for="item in sourceStats" :key="item.key" class="source" :class="{ 'is-empty': item.count === 0 }">
        <SourceBadge :verification="item.key" size="sm" />
        <span class="source__text">{{ item.text }}</span>
      </li>
    </ul>

    <div class="layout">
      <div class="col col--main">
        <CategoryCard class="b-cat" :category="card.category" title="Категория кандидата" show-skills />

        <GradeExplanation class="b-rest" :category="card.category" open />
        <ConfidenceMeter class="b-rest" :category="card.category" />

        <FspTimeline v-if="fspResults.length > 0" class="b-rest" :facts="fspResults" />

        <section v-if="otherFacts.length > 0" class="b-rest facts card" aria-labelledby="facts-title">
          <header class="facts__head">
            <h2 id="facts-title" class="facts__title">Факты профиля</h2>
            <p class="facts__lead">
              У каждого факта указан источник. Значок «Подтверждено» значит, что данные пришли из реестра ФСП или
              из теста платформы, а не со слов кандидата.
              <template v-if="hasHiddenLinks">
                Ссылки на протоколы и документы откроются после принятия оффера.
              </template>
            </p>
          </header>
          <FactList :facts="otherFacts" empty-text="Других фактов в профиле нет." />
        </section>
      </div>

      <div class="col col--side">
        <section class="b-side side card" aria-labelledby="contacts-title">
          <h2 id="contacts-title" class="side__title">
            <AppIcon :name="contactState === 'open' ? 'check' : 'lock'" :size="18" />
            Контакты и полное ФИО
          </h2>

          <template v-if="card.contacts">
            <p class="callout callout--success">Кандидат принял ваш оффер, контакты открыты.</p>
            <p class="contact-name">{{ card.display_name }}</p>
            <ContactLines :contacts="card.contacts" />
          </template>
          <template v-else>
            <p class="locked">Контакты и полное ФИО откроются, когда кандидат примет ваш оффер.</p>
            <p v-if="contactNote" class="callout">{{ contactNote }}</p>
            <p class="side__small">
              Так платформа защищает персональные данные: до согласия кандидата вы видите только имя и первую букву
              фамилии.
            </p>
          </template>
        </section>

        <section class="b-side side card" aria-labelledby="terms-title">
          <h2 id="terms-title" class="side__title">Ожидания и условия</h2>
          <dl class="terms">
            <div class="terms__row">
              <dt>Зарплата</dt>
              <dd><MoneyRange :amount="card.salary_expectation" size="md" empty-text="не указана" /></dd>
            </div>
            <div class="terms__row">
              <dt>Формат работы</dt>
              <dd>{{ formatList(card) }}</dd>
            </div>
            <div class="terms__row">
              <dt>Город</dt>
              <dd>{{ card.city ?? 'не указан' }}</dd>
            </div>
            <div class="terms__row">
              <dt>Переезд</dt>
              <dd>{{ card.relocation ? 'готов' : 'не рассматривает' }}</dd>
            </div>
            <div v-if="card.sport_rank" class="terms__row">
              <dt>Спортивный разряд</dt>
              <dd>{{ reference.rankTitle(card.sport_rank) }}</dd>
            </div>
          </dl>
          <div v-if="card.about" class="about">
            <p class="about__label">О себе</p>
            <p class="about__text">{{ card.about }}</p>
          </div>
        </section>

        <OfferForm
          class="b-offer"
          :card="card"
          :vacancies="vacancies ?? []"
          :status="vacanciesStatus"
          :error-message="vacanciesError"
          :preset-vacancy-id="presetVacancyId"
          @sent="onOfferSent"
          @stale="onStale"
          @retry="loadVacancies"
        />

        <section v-if="card.offers.length > 0" class="b-offer side card" aria-labelledby="prior-title">
          <h2 id="prior-title" class="side__title">Отправленные офферы</h2>
          <ul class="prior">
            <li v-for="offer in card.offers" :key="offer.id" class="prior__item">
              <div class="prior__main">
                <span class="prior__title">{{ offer.vacancy_title }}</span>
                <span class="prior__meta">
                  <MoneyRange :amount="offer.salary" size="sm" />
                  <span class="muted">· {{ formatDate(offer.created_at) }}</span>
                </span>
              </div>
              <OfferStatusBadge :status="offer.status" />
            </li>
          </ul>
        </section>
      </div>
    </div>
  </template>
</template>

<style scoped>
.flip {
  transform: scaleX(-1);
}

/* ----- Sources strip ----- */
.sources {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: var(--sp-2) var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  list-style: none;
}
.source {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px var(--sp-2);
  min-width: 0;
}
.source__text {
  font-size: var(--fs-sm);
  color: var(--c-text);
}
.source.is-empty .source__text {
  color: var(--c-text-muted);
}
.source.is-empty :deep(.badge) {
  opacity: 0.55;
}

/* ----- Layout: on phones the blocks are ordered by the decision flow (category, terms, evidence, offer),
   on desktop the main column and the side column are real columns. ----- */
.layout {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}
.col {
  display: contents;
}
.b-cat {
  order: 1;
}
.b-side {
  order: 2;
}
.b-rest {
  order: 3;
}
.b-offer {
  order: 4;
}

/* ----- Facts ----- */
.facts {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.facts__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.facts__title {
  font-size: var(--fs-lg);
}
.facts__lead {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
  line-height: 1.5;
}

/* ----- Side blocks ----- */
.side {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.side__title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-md);
}
.side__small {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
  line-height: 1.5;
}
.locked {
  font-size: var(--fs-base);
  font-weight: 600;
  line-height: 1.45;
  color: var(--c-ink);
}
.contact-name {
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--c-ink);
}

.terms {
  display: flex;
  flex-direction: column;
  margin: 0;
}
.terms__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-4);
  padding: 9px 0;
  border-bottom: 1px solid var(--c-border);
  font-size: var(--fs-sm);
}
.terms__row:last-child {
  border-bottom: 0;
}
.terms dt {
  color: var(--c-text-muted);
}
.terms dd {
  margin: 0;
  text-align: right;
  font-weight: 500;
}
.about {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--sp-3);
  border-radius: var(--r-md);
  background: var(--c-surface-2);
}
.about__label {
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.about__text {
  font-size: var(--fs-sm);
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.prior {
  display: flex;
  flex-direction: column;
  list-style: none;
}
.prior__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--c-border);
}
.prior__item:last-child {
  border-bottom: 0;
}
.prior__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.prior__title {
  font-size: var(--fs-sm);
  font-weight: 600;
  overflow-wrap: anywhere;
}
.prior__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px;
  font-size: var(--fs-xs);
}

@media (min-width: 1000px) {
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 380px;
    gap: var(--sp-6);
    align-items: start;
  }
  .col {
    display: flex;
    flex-direction: column;
    gap: var(--sp-5);
    min-width: 0;
  }
}
</style>
