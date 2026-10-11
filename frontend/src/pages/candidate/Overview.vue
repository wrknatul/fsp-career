<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import { getProfile } from '@/api/candidate'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import CategoryCard from '@/components/CategoryCard.vue'
import ConfidenceMeter from '@/components/ConfidenceMeter.vue'
import GradeExplanation from '@/components/GradeExplanation.vue'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'
import { useInboxStore } from '@/stores/inbox'
import { formatCount } from '@/utils/format'

import SourceChecklist from './components/SourceChecklist.vue'
import VisibilityCard from './components/VisibilityCard.vue'
import { pickFacts } from './components/helpers'

// Main screen of the candidate: category and why, confirmation index, four sources, visibility, new offers.
const { data: profile, status, errorMessage, load, setData } = useLoader(() => getProfile())
const inbox = useInboxStore()

onMounted(() => {
  void inbox.refresh()
})

type NextStep = { text: string; action: string; to: RouteLocationRaw }

const testsPassed = computed(() => (profile.value === null ? 0 : pickFacts(profile.value.facts, 'skill', 'test').length))

// One concrete next action, in the order of the demo scenario: registry, resume, tests, visibility.
const nextStep = computed<NextStep | null>(() => {
  const current = profile.value
  if (current === null) {
    return null
  }
  if (current.fsp === null) {
    return {
      text: 'Привяжите ФСП: результаты реестра сразу попадут в профиль как подтверждённые.',
      action: 'Привязать ФСП',
      to: '/candidate/fsp',
    }
  }
  if (current.resume === null) {
    return {
      text: 'Добавьте резюме: опыт работы определяет грейд, а без него он не выше Junior.',
      action: 'Добавить резюме',
      to: { path: '/candidate/profile', hash: '#resume' },
    }
  }
  if (testsPassed.value < 2) {
    return {
      text: 'Сдайте экспресс-тест: навык станет подтверждённым, а опыт из резюме засчитается полнее.',
      action: 'К тестам',
      to: '/candidate/tests',
    }
  }
  if (!current.visible) {
    return {
      text: 'Профиль собран, но скрыт. Включите показ, чтобы работодатели могли прислать оффер.',
      action: 'Включить показ',
      to: { path: '/candidate', hash: '#visibility' },
    }
  }
  return null
})

const offersTitle = computed(() =>
  formatCount(inbox.pendingOffers, ['новый оффер', 'новых оффера', 'новых офферов']),
)
</script>

<template>
  <PageHeader
    title="Ваш профиль"
    eyebrow="Соискатель"
    subtitle="Откликаться на вакансии не нужно: платформа сама относит вас к категории по тому, что можно подтвердить, а работодатель приходит с оффером."
  />

  <StateBlock v-if="status === 'loading'" state="loading" title="Собираем ваш профиль…" />
  <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />

  <template v-else-if="profile">
    <section v-if="inbox.pendingOffers > 0" class="offers offers--new" aria-live="polite">
      <span class="offers__count num">{{ inbox.pendingOffers }}</span>
      <div class="offers__text">
        <p class="offers__title">У вас {{ offersTitle }}</p>
        <p class="offers__hint">Компания уже выбрала вас и назвала зарплату. Ответ за вами.</p>
      </div>
      <AppButton to="/candidate/offers" variant="inverse">Посмотреть</AppButton>
    </section>
    <section v-else class="offers" aria-live="polite">
      <span class="offers__count offers__count--zero num">0</span>
      <div class="offers__text">
        <p class="offers__title">Новых офферов пока нет</p>
        <p class="offers__hint">
          Работодатель найдёт вас по категории и пришлёт предложение с зарплатой. Чем больше подтверждено, тем выше вы в выдаче.
        </p>
      </div>
      <AppButton to="/candidate/offers" variant="secondary">Все офферы</AppButton>
    </section>

    <div class="ov">
      <div class="ov__main">
        <CategoryCard :category="profile.category" title="Ваша категория" show-skills>
          <template #undetermined>
            <div class="start">
              <p class="start__title">С чего начать</p>
              <ol class="start__list">
                <li class="start__item">
                  <span class="start__num num" aria-hidden="true">1</span>
                  <div class="start__body">
                    <p class="start__name">Привязать ФСП</p>
                    <p class="start__desc">Самый быстрый путь: результаты реестра дают стек, разряд и подтверждённый навык.</p>
                  </div>
                  <AppButton to="/candidate/fsp" size="sm">Привязать</AppButton>
                </li>
                <li class="start__item">
                  <span class="start__num num" aria-hidden="true">2</span>
                  <div class="start__body">
                    <p class="start__name">Добавить резюме</p>
                    <p class="start__desc">Навыки и опыт работы. Без опыта грейд не поднимется выше Junior.</p>
                  </div>
                  <AppButton :to="{ path: '/candidate/profile', hash: '#resume' }" variant="secondary" size="sm">
                    Добавить
                  </AppButton>
                </li>
                <li class="start__item">
                  <span class="start__num num" aria-hidden="true">3</span>
                  <div class="start__body">
                    <p class="start__name">Сдать экспресс-тест</p>
                    <p class="start__desc">Шесть вопросов по навыку. Результат помечается как подтверждённый тестом.</p>
                  </div>
                  <AppButton to="/candidate/tests" variant="secondary" size="sm">Пройти</AppButton>
                </li>
              </ol>
            </div>
          </template>
          <template v-if="nextStep && profile.category.stack !== null" #footer>
            <div class="next">
              <p class="next__text"><AppIcon name="arrow-right" :size="16" /><span>{{ nextStep.text }}</span></p>
              <AppButton :to="nextStep.to" size="sm">{{ nextStep.action }}</AppButton>
            </div>
          </template>
        </CategoryCard>

        <GradeExplanation :category="profile.category" open />
      </div>

      <aside class="ov__side">
        <ConfidenceMeter :category="profile.category" />
        <div id="visibility">
          <VisibilityCard :profile="profile" @updated="setData" />
        </div>
      </aside>
    </div>

    <section class="stack" aria-labelledby="sources-title">
      <h2 id="sources-title" class="section-title">Источники профиля</h2>
      <SourceChecklist :profile="profile" />
    </section>
  </template>
</template>

<style scoped>
.offers {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--sp-3) var(--sp-4);
  align-items: center;
  padding: var(--sp-4) var(--sp-5);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.offers--new {
  border-color: transparent;
  background: var(--c-ink);
  color: var(--c-on-ink);
}
.offers__count {
  display: grid;
  place-items: center;
  min-width: 48px;
  height: 48px;
  padding-inline: 10px;
  border-radius: var(--r-md);
  background: var(--c-primary);
  color: #fff;
  font-size: var(--fs-xl);
  font-weight: 700;
}
.offers__count--zero {
  background: var(--c-neutral-soft);
  color: var(--c-text-muted);
}
.offers__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.offers__title {
  font-family: var(--font-mono);
  font-weight: 600;
  letter-spacing: -0.02em;
}
.offers__hint {
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-text-muted);
}
.offers--new .offers__hint {
  color: var(--c-on-ink-muted);
}
.offers > :last-child {
  grid-column: 1 / -1;
  justify-self: start;
}

.ov {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-6);
  align-items: start;
}
.ov__main,
.ov__side {
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
  min-width: 0;
}

.start {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  width: 100%;
}
.start__title {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--c-ink);
}
.start__list {
  list-style: none;
  display: flex;
  flex-direction: column;
}
.start__item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: var(--sp-2) var(--sp-3);
  align-items: start;
  padding: var(--sp-3) 0;
  border-top: 1px solid var(--c-border);
}
.start__item > :last-child {
  grid-column: 2;
  justify-self: start;
}
.start__num {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: var(--fs-sm);
  font-weight: 700;
}
.start__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.start__name {
  font-weight: 600;
  color: var(--c-ink);
}
.start__desc {
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-text-muted);
}

.next {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3) var(--sp-4);
}
.next__text {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1 1 260px;
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-ink);
}
.next__text :deep(svg) {
  margin-top: 3px;
  color: var(--c-primary);
}

@media (min-width: 640px) {
  .offers {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }
  .offers > :last-child {
    grid-column: auto;
    justify-self: end;
  }
  .start__item {
    grid-template-columns: 28px minmax(0, 1fr) auto;
    align-items: center;
  }
  .start__item > :last-child {
    grid-column: auto;
    justify-self: end;
  }
}

@media (min-width: 1000px) {
  .ov {
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  }
}
</style>
