<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { listOffers, respondToOffer } from '@/api/candidate'
import { hasErrorCode } from '@/api/client'
import type { CandidateOffer, OfferDecision } from '@/api/types'
import AppTextarea from '@/components/AppTextarea.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { useInboxStore } from '@/stores/inbox'
import { useToastStore } from '@/stores/toast'
import { formatCount } from '@/utils/format'

import OfferCard from './components/OfferCard.vue'

// Incoming offers. The candidate never applies: companies find the profile and come with a salary.
const { data: offers, status, errorMessage, load, setData } = useLoader(() => listOffers())
const inbox = useInboxStore()
const toast = useToastStore()

const MAX_COMMENT = 500

const target = shallowRef<CandidateOffer | null>(null)
const mode = ref<OfferDecision>('accept')
const askConfirm = ref(false)
const comment = ref('')
const sending = ref(false)

function byNewest(a: CandidateOffer, b: CandidateOffer): number {
  return b.created_at.localeCompare(a.created_at) || b.id - a.id
}

// Offers waiting for an answer come first: that is what needs doing. Each group is newest first.
const pending = computed(() => (offers.value ?? []).filter((offer) => offer.status === 'sent').sort(byNewest))
const answered = computed(() => (offers.value ?? []).filter((offer) => offer.status !== 'sent').sort(byNewest))

const subtitle = computed(() => {
  if (pending.value.length === 0) {
    return 'Вы не откликаетесь на вакансии: компании находят ваш профиль и присылают предложение с зарплатой.'
  }
  return `Ждёт вашего ответа: ${formatCount(pending.value.length, ['оффер', 'оффера', 'офферов'])}. Вы не откликались: компании сами нашли ваш профиль.`
})

// Keep the badge on the "Офферы" tab in step with the list this page already holds.
watch(
  pending,
  (list) => {
    if (offers.value !== null) {
      inbox.setPending(list.length)
    }
  },
  { immediate: true },
)

function ask(offer: CandidateOffer, decision: OfferDecision): void {
  target.value = offer
  mode.value = decision
  comment.value = ''
  askConfirm.value = true
}

async function send(): Promise<void> {
  const offer = target.value
  if (offer === null || sending.value) {
    return
  }
  sending.value = true
  try {
    const trimmed = comment.value.trim()
    const updated = await respondToOffer(offer.id, {
      decision: mode.value,
      ...(mode.value === 'decline' && trimmed !== '' ? { comment: trimmed } : {}),
    })
    setData((offers.value ?? []).map((item) => (item.id === updated.id ? updated : item)))
    askConfirm.value = false
    toast.success(
      mode.value === 'accept'
        ? 'Оффер принят. Контакты компании открыты, а компания видит ваше ФИО и контакты.'
        : 'Оффер отклонён',
    )
    void inbox.refresh()
  } catch (err) {
    toast.fromError(err)
    if (hasErrorCode(err, 'OFFER_ALREADY_RESPONDED')) {
      askConfirm.value = false
      await load()
      void inbox.refresh()
    }
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <PageHeader title="Входящие офферы" eyebrow="Соискатель" :subtitle="subtitle" />

  <StateBlock v-if="status === 'loading'" state="loading" title="Загружаем офферы…" />
  <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />
  <StateBlock
    v-else-if="offers && offers.length === 0"
    state="empty"
    title="Офферов пока нет"
    text="Работодатель найдёт вас по категории и пришлёт предложение с зарплатой. Чем больше в профиле подтверждено, тем выше вы в выдаче."
  >
    <template #action>
      <RouterLink to="/candidate" class="link">К обзору профиля</RouterLink>
    </template>
  </StateBlock>

  <template v-else-if="offers">
    <section v-if="pending.length > 0" class="group" aria-labelledby="pending-title">
      <h2 id="pending-title" class="section-title">
        Ждут вашего ответа <span class="group__count num">{{ pending.length }}</span>
      </h2>
      <OfferCard
        v-for="offer in pending"
        :key="offer.id"
        :offer="offer"
        :busy="sending"
        @accept="ask($event, 'accept')"
        @decline="ask($event, 'decline')"
      />
    </section>

    <section v-if="answered.length > 0" class="group" aria-labelledby="answered-title">
      <h2 id="answered-title" class="section-title">
        Вы уже ответили <span class="group__count num">{{ answered.length }}</span>
      </h2>
      <OfferCard v-for="offer in answered" :key="offer.id" :offer="offer" />
    </section>
  </template>

  <ConfirmModal
    v-model="askConfirm"
    :title="mode === 'accept' ? 'Принять оффер?' : 'Отклонить оффер?'"
    :message="
      mode === 'accept'
        ? `Оффер от «${target?.company.name ?? ''}»: после принятия компания увидит ваше ФИО и контакты.`
        : `Оффер от «${target?.company.name ?? ''}» закроется, отменить это нельзя. Компания увидит ваш комментарий, но не ФИО и не контакты.`
    "
    :confirm-label="mode === 'accept' ? 'Принять оффер' : 'Отклонить оффер'"
    :danger="mode === 'decline'"
    :loading="sending"
    @confirm="send"
  >
    <AppTextarea
      v-if="mode === 'decline'"
      v-model="comment"
      label="Комментарий (необязательно)"
      :rows="3"
      :maxlength="MAX_COMMENT"
      placeholder="Например: сейчас не ищу работу или условия не подходят"
      hint="Контакты в тексте комментария будут скрыты от компании."
    />
  </ConfirmModal>
</template>

<style scoped>
.group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.group__count {
  font-weight: 500;
  color: var(--c-text-faint);
}
</style>
