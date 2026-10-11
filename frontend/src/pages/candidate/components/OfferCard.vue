<script setup lang="ts">
import { computed } from 'vue'

import type { CandidateOffer } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import MoneyRange from '@/components/MoneyRange.vue'
import { useReferenceStore } from '@/stores/reference'
import { isHttpUrl } from '@/utils/facts'
import { formatAgo, formatDate } from '@/utils/format'
import { OFFER_STATUS_TITLES } from '@/utils/labels'

// One incoming offer: company with the verification badge, the salary first, the vacancy fork, message and status.
const props = defineProps<{ offer: CandidateOffer; busy?: boolean }>()
const emit = defineEmits<{ accept: [offer: CandidateOffer]; decline: [offer: CandidateOffer] }>()

const reference = useReferenceStore()

const vacancyMeta = computed(() => {
  const vacancy = props.offer.vacancy
  const parts = [reference.stackTitle(vacancy.stack), reference.gradeTitle(vacancy.grade)]
  if (vacancy.work_formats.length > 0) {
    parts.push(reference.joinTitles(vacancy.work_formats, reference.workFormatTitle))
  }
  if (vacancy.city) {
    parts.push(vacancy.city)
  }
  return parts.join(' · ')
})

const website = computed(() => (isHttpUrl(props.offer.company.website) ? props.offer.company.website : null))

const telegramLink = computed(() => {
  const handle = props.offer.employer_contacts?.contact_telegram?.trim() ?? ''
  const bare = handle.replace(/^@/, '')
  return /^[A-Za-z0-9_]{4,32}$/.test(bare) ? `https://t.me/${bare}` : null
})

const isNew = computed(() => props.offer.status === 'sent')

const answeredLine = computed(() => {
  const prefix = props.offer.status === 'accepted' ? 'Вы приняли оффер' : 'Вы отклонили оффер'
  return props.offer.responded_at ? `${prefix} ${formatDate(props.offer.responded_at)}` : prefix
})
</script>

<template>
  <article class="offer card" :class="[`offer--${offer.status}`, { 'is-new': isNew }]">
    <header class="offer__head">
      <div class="offer__company">
        <h2 class="offer__name">{{ offer.company.name }}</h2>
        <span class="trust" :class="offer.company.verified ? 'is-ok' : 'is-no'">
          <AppIcon :name="offer.company.verified ? 'shield' : 'alert'" :size="13" />
          {{ offer.company.verified ? 'Компания проверена' : 'Не проверена' }}
        </span>
      </div>
      <span class="status" :class="`status--${offer.status}`">{{ OFFER_STATUS_TITLES[offer.status] }}</span>
    </header>

    <div class="offer__money">
      <p class="offer__cap">Предлагают вам</p>
      <MoneyRange :amount="offer.salary" size="xl" />
      <p class="offer__range">
        Вилка вакансии:
        <MoneyRange :from="offer.vacancy.salary_from" :to="offer.vacancy.salary_to" size="sm" empty-text="не указана" />
      </p>
    </div>

    <div class="offer__vacancy">
      <p class="offer__vac-title">{{ offer.vacancy.title }}</p>
      <p class="offer__vac-meta">{{ vacancyMeta }}</p>
      <details v-if="offer.vacancy.description" class="offer__desc">
        <summary>Описание вакансии</summary>
        <p>{{ offer.vacancy.description }}</p>
      </details>
    </div>

    <blockquote v-if="offer.message" class="offer__message">
      <p class="offer__cap">Сообщение от компании</p>
      <p>{{ offer.message }}</p>
    </blockquote>

    <p v-if="offer.company.about || website" class="offer__about">
      <template v-if="offer.company.about">{{ offer.company.about }}</template>
      <a v-if="website" :href="website" target="_blank" rel="noopener noreferrer" class="offer__site">
        Сайт компании <AppIcon name="external" :size="13" />
      </a>
    </p>

    <p class="offer__date">Получен {{ formatAgo(offer.created_at) }}</p>

    <footer v-if="offer.status === 'sent'" class="offer__actions">
      <AppButton :disabled="busy" @click="emit('accept', offer)">Принять</AppButton>
      <AppButton variant="secondary" :disabled="busy" @click="emit('decline', offer)">Отклонить</AppButton>
    </footer>

    <section v-else-if="offer.status === 'accepted'" class="offer__result offer__result--ok">
      <p class="offer__result-title"><AppIcon name="check" :size="16" /><span>{{ answeredLine }}</span></p>
      <dl v-if="offer.employer_contacts" class="contacts">
        <div v-if="offer.employer_contacts.contact_name" class="contacts__row">
          <dt>Контактное лицо</dt>
          <dd>{{ offer.employer_contacts.contact_name }}</dd>
        </div>
        <div v-if="offer.employer_contacts.contact_email" class="contacts__row">
          <dt>Почта</dt>
          <dd><a :href="`mailto:${offer.employer_contacts.contact_email}`">{{ offer.employer_contacts.contact_email }}</a></dd>
        </div>
        <div v-if="offer.employer_contacts.contact_telegram" class="contacts__row">
          <dt>Telegram</dt>
          <dd>
            <a v-if="telegramLink" :href="telegramLink" target="_blank" rel="noopener noreferrer">
              {{ offer.employer_contacts.contact_telegram }}
            </a>
            <template v-else>{{ offer.employer_contacts.contact_telegram }}</template>
          </dd>
        </div>
      </dl>
      <p v-else class="offer__nocontacts">Компания пока не оставила контактов. Они появятся здесь, когда она их добавит.</p>
      <p class="offer__seen">Компания видит ваше полное ФИО и контакты из анкеты.</p>
      <p v-if="offer.candidate_comment" class="offer__comment"><b>Ваш комментарий:</b> {{ offer.candidate_comment }}</p>
    </section>

    <section v-else class="offer__result">
      <p class="offer__result-title"><AppIcon name="x" :size="16" /><span>{{ answeredLine }}</span></p>
      <p v-if="offer.candidate_comment" class="offer__comment"><b>Ваш комментарий:</b> {{ offer.candidate_comment }}</p>
    </section>
  </article>
</template>

<style scoped>
.offer {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.offer.is-new {
  border-color: var(--c-primary);
  box-shadow: 0 0 0 3px var(--c-primary-soft), var(--shadow-sm);
}
.offer__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-2) var(--sp-4);
}
.offer__company {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2) var(--sp-3);
  min-width: 0;
}
.offer__name {
  font-size: var(--fs-lg);
  overflow-wrap: anywhere;
}
.trust {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 600;
  white-space: nowrap;
}
.trust.is-ok {
  background: var(--c-success-soft);
  color: var(--c-success-text);
}
.trust.is-no {
  background: var(--c-warning-soft);
  color: var(--c-warning-text);
}
.status {
  padding: 3px 12px;
  border-radius: var(--r-pill);
  font-size: var(--fs-xs);
  font-weight: 700;
  white-space: nowrap;
}
.status--sent {
  background: var(--c-primary);
  color: #fff;
}
.status--accepted {
  background: var(--c-success-soft);
  color: var(--c-success-text);
}
.status--declined {
  background: var(--c-neutral-soft);
  color: var(--c-neutral-text);
}
.offer__money {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.offer__cap {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.offer__range {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.offer__range :deep(.money) {
  font-weight: 600;
  color: var(--c-text);
}
.offer__vacancy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
}
.offer__vac-title {
  font-weight: 600;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.offer__vac-meta {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.offer__desc {
  margin-top: var(--sp-2);
  font-size: var(--fs-sm);
}
.offer__desc summary {
  cursor: pointer;
  font-weight: 500;
  color: var(--c-primary);
}
.offer__desc p {
  margin-top: var(--sp-2);
  white-space: pre-line;
  line-height: 1.6;
  color: var(--c-text-muted);
}
.offer__message {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: var(--sp-3) var(--sp-4);
  border-left: 3px solid var(--c-primary);
  border-radius: 0 var(--r-md) var(--r-md) 0;
  background: var(--c-surface-2);
  line-height: 1.55;
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.offer__about {
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--c-text-muted);
}
.offer__site {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 6px;
  font-weight: 500;
}
.offer__date {
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.offer__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}
.offer__result {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
  border-radius: var(--r-md);
  background: var(--c-surface-2);
  border: 1px solid var(--c-border);
}
.offer__result--ok {
  background: var(--c-success-soft);
  border-color: var(--c-success-border);
}
.offer__result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.offer__result--ok .offer__result-title {
  color: var(--c-success-text);
}
.contacts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-3) var(--sp-5);
  margin: 0;
}
.contacts__row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.contacts__row dt {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.contacts__row dd {
  margin: 0;
  font-weight: 600;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.offer__nocontacts,
.offer__seen {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.offer__comment {
  font-size: var(--fs-sm);
  overflow-wrap: anywhere;
}
</style>
