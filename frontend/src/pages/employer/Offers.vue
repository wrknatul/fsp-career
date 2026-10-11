<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { listEmployerOffers } from '@/api/employer'
import type { EmployerOffer, OfferStatus } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ChipSelect from '@/components/ChipSelect.vue'
import MoneyRange from '@/components/MoneyRange.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { formatDate, formatMoney, parseServerDate } from '@/utils/format'

import ContactLines from './components/ContactLines.vue'
import OfferStatusBadge from './components/OfferStatusBadge.vue'

// Sent offers, the newest on top: candidate, vacancy, salary, status, the date and the comment of the answer.
// For accepted offers the full name and the contacts are open.

type StatusFilter = OfferStatus | 'all'

const { data, status, errorMessage, load } = useLoader(() => listEmployerOffers())

const filter = ref<StatusFilter[]>(['all'])
/** An empty selection (the chip pressed twice) means "all". */
const activeFilter = computed<StatusFilter>(() => filter.value[0] ?? 'all')

function timeOf(offer: EmployerOffer): number {
  return parseServerDate(offer.created_at)?.getTime() ?? 0
}

const offers = computed(() => [...(data.value ?? [])].sort((a, b) => timeOf(b) - timeOf(a)))

function countOf(offerStatus: OfferStatus): number {
  return offers.value.filter((offer) => offer.status === offerStatus).length
}

const filterOptions = computed<{ value: StatusFilter; label: string }[]>(() => [
  { value: 'all', label: `Все · ${offers.value.length}` },
  { value: 'sent', label: `Ждут ответа · ${countOf('sent')}` },
  { value: 'accepted', label: `Приняты · ${countOf('accepted')}` },
  { value: 'declined', label: `Отклонены · ${countOf('declined')}` },
])

const shown = computed(() =>
  activeFilter.value === 'all' ? offers.value : offers.value.filter((offer) => offer.status === activeFilter.value),
)

function belowExpectation(offer: EmployerOffer): number {
  const expected = offer.candidate.salary_expectation
  return expected !== null && offer.salary < expected ? expected - offer.salary : 0
}
</script>

<template>
  <PageHeader
    title="Отправленные офферы"
    eyebrow="Работодатель"
    subtitle="Здесь видно, кому вы предложили работу, сколько и что ответил кандидат. Контакты и полное ФИО открываются только у принятых офферов."
  >
    <template #actions>
      <AppButton variant="secondary" :to="{ name: 'employer-search' }">
        <AppIcon name="search" :size="18" />
        Найти кандидатов
      </AppButton>
    </template>
  </PageHeader>

  <StateBlock v-if="status === 'loading' || status === 'idle'" state="loading" title="Загружаем офферы…" />
  <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />

  <StateBlock
    v-else-if="offers.length === 0"
    state="empty"
    title="Вы пока не отправляли офферы"
    text="Найдите кандидата, посмотрите, чем подтверждён его профиль, и предложите работу с зарплатой. Контакты откроются, когда он согласится."
  >
    <template #action>
      <AppButton :to="{ name: 'employer-search' }">Перейти к поиску</AppButton>
      <AppButton variant="secondary" :to="{ name: 'employer-dashboard' }">Витрина категорий</AppButton>
    </template>
  </StateBlock>

  <template v-else>
    <ChipSelect v-model="filter" :options="filterOptions" label="Статус" single />

    <StateBlock
      v-if="shown.length === 0"
      state="empty"
      title="С таким статусом офферов нет"
      text="Выберите другой статус или покажите все офферы."
    >
      <template #action>
        <AppButton variant="secondary" @click="filter = ['all']">Показать все</AppButton>
      </template>
    </StateBlock>

    <div v-else class="offers">
      <article v-for="offer in shown" :key="offer.id" class="offer card" :class="`offer--${offer.status}`">
        <header class="offer__head">
          <div class="offer__who">
            <h2 class="offer__name">
              <RouterLink
                class="offer__link"
                :to="{ name: 'employer-candidate', params: { id: String(offer.candidate.id) } }"
              >
                {{ offer.candidate.display_name }}
              </RouterLink>
            </h2>
            <p class="offer__category">{{ offer.candidate.category.label }}</p>
          </div>
          <OfferStatusBadge :status="offer.status" />
        </header>

        <dl class="offer__facts">
          <div class="fact">
            <dt>Вакансия</dt>
            <dd>{{ offer.vacancy.title }}</dd>
          </div>
          <div class="fact">
            <dt>Зарплата в оффере</dt>
            <dd><MoneyRange :amount="offer.salary" size="lg" /></dd>
          </div>
          <div class="fact">
            <dt>Ожидания кандидата</dt>
            <dd>
              <MoneyRange :amount="offer.candidate.salary_expectation" size="md" empty-text="не указаны" />
              <span v-if="belowExpectation(offer) > 0" class="fact__note">
                оффер ниже на {{ formatMoney(belowExpectation(offer)) }}
              </span>
            </dd>
          </div>
          <div class="fact">
            <dt>Отправлен</dt>
            <dd class="num">{{ formatDate(offer.created_at) }}</dd>
          </div>
          <div class="fact">
            <dt>Ответ</dt>
            <dd v-if="offer.responded_at" class="num">{{ formatDate(offer.responded_at) }}</dd>
            <dd v-else class="muted">ждём ответа</dd>
          </div>
        </dl>

        <blockquote v-if="offer.message" class="quote">
          <p class="quote__label">Ваше сообщение</p>
          <p class="quote__text">{{ offer.message }}</p>
        </blockquote>

        <blockquote v-if="offer.candidate_comment" class="quote quote--reply">
          <p class="quote__label">Комментарий кандидата</p>
          <p class="quote__text">{{ offer.candidate_comment }}</p>
        </blockquote>

        <section v-if="offer.contacts" class="open callout callout--success" aria-label="Контакты кандидата">
          <div class="open__body">
            <p class="open__title">
              <AppIcon name="check" :size="16" />
              Кандидат принял оффер: контакты открыты
            </p>
            <p class="open__name">{{ offer.candidate.display_name }}</p>
            <ContactLines :contacts="offer.contacts" />
          </div>
        </section>
        <p v-else-if="offer.status === 'sent'" class="hidden-note">
          <AppIcon name="lock" :size="14" />
          Контакты и полное ФИО откроются, если кандидат примет оффер.
        </p>
        <p v-else-if="offer.status === 'declined'" class="hidden-note">
          <AppIcon name="lock" :size="14" />
          Кандидат отказался, контакты остаются скрытыми.
        </p>

        <footer class="offer__foot">
          <AppButton
            variant="secondary"
            size="sm"
            :to="{ name: 'employer-candidate', params: { id: String(offer.candidate.id) } }"
          >
            Открыть карточку
          </AppButton>
        </footer>
      </article>
    </div>
  </template>
</template>

<style scoped>
.offers {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.offer {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
  border-left: 4px solid var(--c-border-strong);
}
.offer--sent {
  border-left-color: var(--c-warning);
}
.offer--accepted {
  border-left-color: var(--c-success);
}
.offer--declined {
  border-left-color: var(--c-danger);
}
.offer__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
}
.offer__who {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.offer__name {
  font-size: var(--fs-lg);
  letter-spacing: -0.03em;
}
.offer__link {
  color: var(--c-ink);
  text-decoration: none;
}
.offer__link:hover {
  color: var(--c-primary);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.offer__category {
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--c-text-muted);
  line-height: 1.4;
}

.offer__facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: var(--sp-3) var(--sp-5);
  margin: 0;
}
.fact {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.fact dt {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.fact dd {
  display: flex;
  flex-direction: column;
  margin: 0;
  font-size: var(--fs-sm);
  font-weight: 500;
  overflow-wrap: anywhere;
}
.fact__note {
  font-size: var(--fs-xs);
  font-weight: 500;
  color: var(--c-warning-text);
}

.quote {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin: 0;
  padding: var(--sp-3) var(--sp-4);
  border-left: 3px solid var(--c-border-strong);
  border-radius: 0 var(--r-md) var(--r-md) 0;
  background: var(--c-surface-2);
}
.quote--reply {
  border-left-color: var(--c-primary);
  background: var(--c-primary-soft);
}
.quote__label {
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.quote__text {
  font-size: var(--fs-sm);
  line-height: 1.55;
  white-space: pre-line;
  overflow-wrap: anywhere;
}

.open {
  padding: var(--sp-4);
}
.open__body {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  min-width: 0;
}
.open__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}
.open__name {
  font-family: var(--font-mono);
  font-size: var(--fs-md);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--c-ink);
}
.hidden-note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.offer__foot {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}
</style>
