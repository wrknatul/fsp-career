<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { getProfile, linkFsp, unlinkFsp } from '@/api/candidate'
import type { Category, FspLinkResult, SportRank } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppInput from '@/components/AppInput.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import PageHeader from '@/components/PageHeader.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import StatTile from '@/components/StatTile.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { DEMO_FSP_ID, DEMO_MODE } from '@/utils/demo'
import { rankFactValue } from '@/utils/facts'
import { formatDate } from '@/utils/format'

import CategoryChange from './components/CategoryChange.vue'
import FspResults from './components/FspResults.vue'
import { describeLinkError, pickFacts, type LinkErrorView } from './components/helpers'

// The centrepiece of the demo: link the FSP registry record and watch the profile become "verified".
const { data: profile, status, errorMessage, load, setData } = useLoader(() => getProfile())
const reference = useReferenceStore()
const toast = useToastStore()

type LinkSummary = { shortName: string; imported: FspLinkResult['imported']; before: Category; after: Category }

const fspId = ref('')
const linking = ref(false)
const linkError = ref<LinkErrorView | null>(null)
const summary = ref<LinkSummary | null>(null)
const askUnlink = ref(false)
const unlinking = ref(false)

// Linking compares the questionnaire with the registry: both name and birth date must be filled in.
const missingFields = computed<string[]>(() => {
  const current = profile.value
  if (current === null) {
    return []
  }
  const missing: string[] = []
  if (current.user.full_name.trim() === '') missing.push('ФИО')
  if (current.birth_date === null) missing.push('дата рождения')
  return missing
})

const showDemoHint = computed(() => DEMO_MODE || reference.isMock)

// Counters: straight from the link response right after linking, otherwise counted from the facts.
const counters = computed(() => {
  const current = profile.value
  if (current === null) {
    return { achievements: 0, ranks: 0, skills: 0, roles: 0 }
  }
  if (summary.value !== null) {
    return summary.value.imported
  }
  return {
    achievements: pickFacts(current.facts, 'achievement', 'fsp').length,
    ranks: pickFacts(current.facts, 'rank', 'fsp').length,
    skills: pickFacts(current.facts, 'skill', 'fsp').length,
    roles: pickFacts(current.facts, 'role', 'fsp').length,
  }
})

// Short form for the big tile: the full title ("Мастер спорта России") does not fit in a large mono font.
const RANK_SHORT: Record<SportRank, string> = {
  third: 'III',
  second: 'II',
  first: 'I',
  kms: 'КМС',
  ms: 'МС',
}

const rank = computed(() => {
  const fact = profile.value === null ? undefined : pickFacts(profile.value.facts, 'rank', 'fsp')[0]
  if (fact === undefined) {
    return null
  }
  const value = rankFactValue(fact)
  const parts: string[] = []
  if (value.discipline !== null) parts.push(reference.disciplineTitle(value.discipline))
  if (value.assigned_at !== null) parts.push(`присвоен ${formatDate(value.assigned_at)}`)
  if (value.order_no !== null) parts.push(`приказ ${value.order_no}`)
  return { title: reference.rankTitle(value.rank), short: RANK_SHORT[value.rank] ?? '—', meta: parts.join(' · ') }
})

function fillDemoId(): void {
  fspId.value = DEMO_FSP_ID
  linkError.value = null
}

async function refreshQuietly(): Promise<void> {
  try {
    setData(await getProfile())
  } catch {
    // The page keeps what it has; the next action will surface a real error.
  }
}

async function link(): Promise<void> {
  if (linking.value || profile.value === null) {
    return
  }
  const id = fspId.value.trim().toUpperCase()
  if (id === '') {
    linkError.value = { text: 'Введите ФСП ID, например FSP-2024-00117.', toProfile: false, reload: false }
    return
  }
  if (missingFields.value.length > 0) {
    return
  }
  const before = profile.value.category
  linking.value = true
  linkError.value = null
  try {
    const result = await linkFsp(id)
    summary.value = { shortName: result.athlete.short_name, imported: result.imported, before, after: result.profile.category }
    setData(result.profile)
    fspId.value = ''
    toast.success(`ФСП привязан: ${result.athlete.short_name}`)
  } catch (err) {
    const view = describeLinkError(err)
    if (view === null) {
      toast.fromError(err)
    } else {
      linkError.value = view
      if (view.reload) {
        await refreshQuietly()
      }
    }
  } finally {
    linking.value = false
  }
}

async function unlink(): Promise<void> {
  if (unlinking.value) {
    return
  }
  unlinking.value = true
  try {
    setData(await unlinkFsp())
    summary.value = null
    askUnlink.value = false
    toast.info('ФСП отвязан. Результаты реестра убраны из профиля, категория пересчитана.')
  } catch (err) {
    toast.fromError(err)
  } finally {
    unlinking.value = false
  }
}
</script>

<template>
  <PageHeader
    title="Привязка к ФСП"
    eyebrow="Соискатель"
    subtitle="Результаты Федерации спортивного программирования — самое сильное подтверждение в профиле: их проверяет не платформа, а реестр."
  />

  <StateBlock v-if="status === 'loading'" state="loading" title="Загружаем данные ФСП…" />
  <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />

  <!-- Not linked -->
  <div v-else-if="profile && profile.fsp === null" class="intro">
    <section class="card benefits">
      <h2 class="h3">Что даёт привязка</h2>
      <ul class="benefits__list">
        <li>
          <AppIcon name="check" :size="16" />
          <span>Каждый результат попадёт в профиль с отметкой <SourceBadge verification="verified" size="sm" /> и ссылкой на протокол.</span>
        </li>
        <li>
          <AppIcon name="check" :size="16" />
          <span>Разряд и навыки по дисциплинам подтвердятся автоматически, а по ним платформа определит ваш стек.</span>
        </li>
        <li>
          <AppIcon name="check" :size="16" />
          <span>Индекс подтверждённости вырастет на 50 из 100: это половина шкалы.</span>
        </li>
        <li>
          <AppIcon name="check" :size="16" />
          <span>Грейд и категория пересчитаются при вас, а причины будут видны на обзоре.</span>
        </li>
      </ul>
    </section>

    <section class="card form" aria-labelledby="link-title">
      <h2 id="link-title" class="h3">Привязать ФСП ID</h2>

      <p v-if="missingFields.length > 0" class="callout callout--warning">
        <AppIcon name="alert" :size="16" />
        <span>
          В анкете не заполнено: {{ missingFields.join(' и ') }}. Привязка сверяет ФИО и дату рождения с реестром, без них она не пройдёт.
          <RouterLink :to="{ path: '/candidate/profile', hash: '#questionnaire' }" class="link">Заполнить анкету</RouterLink>
        </span>
      </p>

      <AppInput
        v-model="fspId"
        label="ФСП ID"
        placeholder="FSP-2024-00117"
        autocomplete="off"
        name="fsp_id"
        :disabled="linking"
        :error="linkError?.text"
        @enter="link"
      />

      <p v-if="linkError?.toProfile" class="form__goto">
        <RouterLink :to="{ path: '/candidate/profile', hash: '#questionnaire' }" class="link">Открыть анкету</RouterLink>
      </p>

      <p v-if="showDemoHint" class="form__demo">
        <AppIcon name="info" :size="16" />
        <span>
          Демо: для демо-аккаунта подойдёт ID <b class="mono">{{ DEMO_FSP_ID }}</b>.
          <button type="button" class="form__fill link" @click="fillDemoId">Подставить</button>
        </span>
      </p>

      <AppButton :loading="linking" :disabled="missingFields.length > 0" block @click="link">Привязать</AppButton>

      <p class="form__honest">
        Привязка по ФСП ID и совпадению ФИО и даты рождения. В демо реестр смоделирован, в рабочей версии — вход через
        аккаунт ФСП.
      </p>
    </section>
  </div>

  <!-- Linked -->
  <template v-else-if="profile && profile.fsp">
    <section class="card linked">
      <div class="linked__top">
        <div class="linked__id">
          <p class="eyebrow">ФСП привязан</p>
          <p class="linked__num num">{{ profile.fsp.fsp_id }}</p>
          <p class="linked__meta">
            <template v-if="profile.fsp.region">{{ profile.fsp.region }} · </template>
            привязан {{ formatDate(profile.fsp.linked_at) }}
          </p>
        </div>
        <div class="linked__actions">
          <SourceBadge verification="verified" />
          <AppButton variant="danger" size="sm" @click="askUnlink = true">Отвязать</AppButton>
        </div>
      </div>

      <dl class="linked__facts">
        <div class="linked__fact">
          <dt>Категория сейчас</dt>
          <dd>
            <span class="linked__label">{{ profile.category.label }}</span>
            <RouterLink to="/candidate" class="link text-sm">Почему такой грейд</RouterLink>
          </dd>
        </div>
        <div v-if="rank" class="linked__fact">
          <dt>Разряд</dt>
          <dd>
            <span class="linked__label">{{ rank.title }}</span>
            <span v-if="rank.meta" class="muted text-sm">{{ rank.meta }}</span>
          </dd>
        </div>
      </dl>

      <p class="form__honest">
        Привязано по ФСП ID и совпадению ФИО и даты рождения. В демо реестр смоделирован; в рабочей версии — вход через
        аккаунт ФСП.
      </p>
    </section>

    <section class="stack" aria-labelledby="imported-title">
      <h2 id="imported-title" class="section-title">Что подтянулось</h2>
      <div class="tiles">
        <StatTile label="Результатов" :value="counters.achievements" hint="соревнований" tone="primary" />
        <StatTile label="Разряд" :value="rank ? rank.short : '—'" hint="звание из реестра" />
        <StatTile label="Навыков" :value="counters.skills" hint="по дисциплинам" />
        <StatTile label="Ролей" :value="counters.roles" hint="в командах" />
      </div>
      <p v-if="summary" class="imported__who">
        Найдена запись «{{ summary.shortName }}» — все эти факты помечены «Подтверждено ФСП».
      </p>
    </section>

    <CategoryChange v-if="summary" :before="summary.before" :after="summary.after" title="Как изменилась категория" />

    <section class="stack" aria-labelledby="results-title">
      <h2 id="results-title" class="section-title">Результаты по годам</h2>
      <div class="card">
        <FspResults v-if="counters.achievements > 0" :facts="profile.facts" />
        <StateBlock
          v-else
          state="empty"
          compact
          title="В реестре пока нет результатов"
          text="Запись привязана, но соревнований в ней нет. Разряд и навыки, если они есть в реестре, учтены."
        />
      </div>
    </section>
  </template>

  <ConfirmModal
    v-model="askUnlink"
    title="Отвязать ФСП?"
    message="Результаты из реестра, разряд и подтверждённые ими навыки исчезнут из профиля. Категория и грейд пересчитаются без них."
    confirm-label="Отвязать"
    danger
    :loading="unlinking"
    @confirm="unlink"
  />
</template>

<style scoped>
.intro {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-6);
  align-items: start;
}
.benefits,
.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.benefits__list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.benefits__list li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  line-height: 1.5;
}
.benefits__list li > :deep(svg) {
  margin-top: 4px;
  color: var(--c-success-text);
}
.form {
  border-color: var(--c-primary-soft-2);
  box-shadow: var(--shadow-md);
}
.form__goto {
  margin-top: -8px;
  font-size: var(--fs-sm);
}
.form__demo {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-md);
  background: var(--c-primary-soft);
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-ink);
}
.form__demo :deep(svg) {
  margin-top: 3px;
  color: var(--c-primary);
}
.form__fill {
  padding: 0;
  border: 0;
  background: none;
  font-size: inherit;
}
.form__honest {
  font-size: var(--fs-xs);
  line-height: 1.5;
  color: var(--c-text-muted);
}

.linked {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}
.linked__top {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
}
.linked__id {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.linked__num {
  font-size: clamp(1.5rem, 1.2rem + 1.4vw, 2.25rem);
  font-weight: 700;
  line-height: 1.1;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.linked__meta {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.linked__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
}
.linked__facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--sp-4) var(--sp-6);
  margin: 0;
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
}
.linked__fact {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.linked__fact dt {
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--c-text-muted);
}
.linked__fact dd {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  margin: 0;
}
.linked__label {
  font-family: var(--font-mono);
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.3;
  color: var(--c-ink);
  overflow-wrap: anywhere;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--sp-3);
}
.imported__who {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}

@media (min-width: 900px) {
  .intro {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: var(--sp-8);
  }
}
</style>
