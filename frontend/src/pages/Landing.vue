<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import type { Role } from '@/api/types'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import ScoreRing from '@/components/ScoreRing.vue'
import SourceBadge from '@/components/SourceBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { useReferenceStore } from '@/stores/reference'
import { useToastStore } from '@/stores/toast'
import { DEMO_MODE } from '@/utils/demo'
import { formatMoney } from '@/utils/format'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()
const reference = useReferenceStore()

const demoLoading = ref<Role | null>(null)

async function enterDemo(role: Role): Promise<void> {
  demoLoading.value = role
  try {
    await auth.demoLogin(role)
    await router.push(auth.homePath)
  } catch (err) {
    toast.fromError(err, 'Не удалось войти в демо. Проверьте, что сервер запущен, и попробуйте ещё раз.')
  } finally {
    demoLoading.value = null
  }
}

const candidateSteps = [
  {
    title: 'Соберите профиль',
    text: 'Привяжите ФСП ID, загрузите резюме, пройдите экспресс-тест. Каждый факт получает источник и уровень подтверждения.',
  },
  {
    title: 'Получите категорию',
    text: 'Платформа сама определит стек, грейд, роль и формат работы — и покажет, из чего сложился грейд.',
  },
  {
    title: 'Принимайте офферы',
    text: 'Работодатель находит вашу категорию и пишет первым — с вакансией и зарплатой. Откликов нет совсем.',
  },
] as const

const employerSteps = [
  {
    title: 'Найдите категорию',
    text: 'Витрина «стек × грейд» показывает, сколько специалистов есть в каждой клетке и сколько из них с результатами ФСП.',
  },
  {
    title: 'Проверьте, чем подтверждено',
    text: 'У каждого навыка и достижения видно источник. Неподтверждённое помечено, оценка поиска раскладывается на части.',
  },
  {
    title: 'Отправьте оффер с зарплатой',
    text: 'Контакты и полное имя откроются, когда кандидат примет оффер. До этого — только имя с первой буквой фамилии.',
  },
] as const

const sources = [
  {
    verification: 'verified',
    weight: 1,
    title: 'Реестр ФСП',
    text: 'Результаты соревнований и спортивные разряды. Привязка по ФСП ID, ФИО и дате рождения.',
  },
  {
    verification: 'tested',
    weight: 0.85,
    title: 'Тест платформы',
    text: 'Экспресс-проверка из 6 вопросов по навыку. Ориентир, а не аттестация.',
  },
  {
    verification: 'parsed',
    weight: 0.55,
    title: 'Резюме',
    text: 'Навыки и опыт, найденные в тексте резюме по правилам, без внешних сервисов.',
  },
  {
    verification: 'declared',
    weight: 0.35,
    title: 'Указано вами',
    text: 'Олимпиады, хакатоны и CTF, которые вы вписали вручную. Вклад в грейд — 35%.',
  },
] as const

const principles = [
  {
    icon: 'search',
    title: 'Объяснимо',
    text: 'У грейда есть раскрываемое «почему», у каждого результата поиска — разбор оценки.',
  },
  {
    icon: 'shield',
    title: 'Честно',
    text: 'Неподтверждённое не прячется: стек и грейд без подтверждения помечены прямо в карточке.',
  },
  {
    icon: 'lock',
    title: 'Приватно',
    text: 'Данные не уходят на внешние сервисы. Работодатель не видит контакты до принятого оффера.',
  },
] as const
</script>

<template>
  <div class="landing">
    <!-- Hero -->
    <section class="hero">
      <div class="container hero__inner">
        <div class="hero__copy">
          <p class="hero__eyebrow">Обратный найм для ИТ</p>
          <h1 class="hero__title">Не откликайтесь. Подтверждайте — и получайте офферы.</h1>
          <p class="hero__lead">
            ФСП.Карьера собирает профиль специалиста из подтверждаемых источников: реестра Федерации спортивного
            программирования, тестов и резюме. Платформа сама определяет категорию, а работодатель приходит с
            оффером и зарплатой.
          </p>

          <div class="hero__actions">
            <template v-if="auth.isAuthenticated">
              <AppButton :to="auth.homePath" size="lg">Перейти в кабинет</AppButton>
            </template>
            <template v-else-if="DEMO_MODE">
              <AppButton size="lg" :loading="demoLoading === 'candidate'" :disabled="demoLoading !== null" @click="enterDemo('candidate')">
                Войти в демо как соискатель
              </AppButton>
              <AppButton variant="outline-inverse" size="lg" :loading="demoLoading === 'employer'" :disabled="demoLoading !== null" @click="enterDemo('employer')">
                Войти в демо как работодатель
              </AppButton>
            </template>
            <template v-else>
              <AppButton :to="{ name: 'register' }" size="lg">Создать аккаунт</AppButton>
              <AppButton :to="{ name: 'login' }" variant="outline-inverse" size="lg">Войти</AppButton>
            </template>
          </div>

          <p v-if="!auth.isAuthenticated" class="hero__fine">
            <template v-if="DEMO_MODE">
              Демо-аккаунты с вымышленными данными: регистрация не нужна. Соискатель начинает с пустого профиля,
              работодатель — с готовой витриной.
              <RouterLink :to="{ name: 'register' }">Создать свой аккаунт</RouterLink>
            </template>
            <template v-else>
              Уже есть аккаунт? Войдите, чтобы продолжить.
            </template>
          </p>
        </div>

        <!-- Static sample card: shows the product idea at a glance. -->
        <aside class="sample" aria-label="Пример карточки кандидата">
          <p class="sample__tag">Пример карточки · данные вымышлены</p>
          <div class="sample__top">
            <div class="sample__who">
              <p class="sample__name">Алексей С.</p>
              <p class="sample__city">Казань · готов к удалёнке</p>
            </div>
            <ScoreRing :value="84" :size="68" caption="из 100" />
          </div>
          <p class="sample__cat">Backend · Middle</p>
          <div class="sample__badges">
            <SourceBadge verification="verified" size="sm" />
            <SourceBadge verification="tested" size="sm" />
            <SourceBadge verification="parsed" size="sm" />
          </div>
          <ul class="sample__facts">
            <li><AppIcon name="check" :size="14" />КМС по алгоритмическому программированию</li>
            <li><AppIcon name="check" :size="14" />Всероссийский уровень, 3 место</li>
            <li><AppIcon name="check" :size="14" />Python — тест, уровень «Уверенный»</li>
          </ul>
          <div class="sample__foot">
            <span>Ожидания по зарплате</span>
            <strong class="num">{{ formatMoney(120000) }}</strong>
          </div>
        </aside>
      </div>
    </section>

    <!-- How it works -->
    <section id="how" class="section">
      <div class="container stack-lg">
        <div class="section__head">
          <p class="eyebrow">Как это работает</p>
          <h2 class="section__title">Две стороны, один принцип: кнопки «откликнуться» нет</h2>
        </div>

        <div class="grid-2 sides">
          <article class="card card--lg side">
            <h3 class="side__title">Соискателю</h3>
            <ol class="steps">
              <li v-for="(step, index) in candidateSteps" :key="step.title" class="step">
                <span class="step__num num">{{ index + 1 }}</span>
                <div>
                  <h4 class="step__title">{{ step.title }}</h4>
                  <p class="step__text">{{ step.text }}</p>
                </div>
              </li>
            </ol>
          </article>

          <article class="card card--lg side">
            <h3 class="side__title">Работодателю</h3>
            <ol class="steps">
              <li v-for="(step, index) in employerSteps" :key="step.title" class="step">
                <span class="step__num num">{{ index + 1 }}</span>
                <div>
                  <h4 class="step__title">{{ step.title }}</h4>
                  <p class="step__text">{{ step.text }}</p>
                </div>
              </li>
            </ol>
          </article>
        </div>
      </div>
    </section>

    <!-- Sources -->
    <section class="section section--alt">
      <div class="container stack-lg">
        <div class="section__head">
          <p class="eyebrow">Источники профиля</p>
          <h2 class="section__title">Четыре источника — и у каждого свой вес доверия</h2>
          <p class="lead">
            Чем надёжнее источник, тем сильнее факт влияет на грейд и на место в поиске. Резюме и самозаявленные
            достижения не могут перебить результат ФСП или сданный тест.
          </p>
        </div>

        <div class="grid-4">
          <article v-for="source in sources" :key="source.title" class="card source">
            <SourceBadge :verification="source.verification" />
            <h3 class="source__title">{{ source.title }}</h3>
            <p class="source__text">{{ source.text }}</p>
            <div class="source__weight">
              <span class="source__weight-label">Вес доверия</span>
              <span class="source__weight-value num">{{ source.weight.toFixed(2).replace('.', ',') }}</span>
            </div>
            <div class="source__bar" aria-hidden="true">
              <span class="source__bar-fill" :style="{ width: `${source.weight * 100}%` }"></span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <!-- Principles -->
    <section class="section">
      <div class="container stack-lg">
        <div class="grid-3">
          <article v-for="item in principles" :key="item.title" class="principle">
            <span class="principle__icon"><AppIcon :name="item.icon" :size="22" /></span>
            <h3 class="principle__title">{{ item.title }}</h3>
            <p class="principle__text">{{ item.text }}</p>
          </article>
        </div>

        <div class="callout callout--primary honesty" role="note">
          <AppIcon name="info" :size="20" />
          <div>
            <p class="honesty__title">Честно про демо</p>
            <p v-if="reference.registryMode !== 'live'">
              Доступа к настоящему реестру ФСП у нас нет, поэтому спортсмены, соревнования и протоколы в этом стенде
              вымышлены. Логика привязки, подтверждения и подсчёта грейда — настоящая. В рабочей версии вместо ввода
              ФСП ID будет вход через аккаунт ФСП.
              <RouterLink :to="{ name: 'privacy' }">Что мы делаем с данными</RouterLink>
            </p>
            <p v-else>
              Стенд подключён к реестру ФСП в рабочем режиме. Привязка проходит по ФСП ID, ФИО и дате рождения.
              <RouterLink :to="{ name: 'privacy' }">Что мы делаем с данными</RouterLink>
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Final call -->
    <section class="cta">
      <div class="container cta__inner">
        <h2 class="cta__title">Посмотрите, как это выглядит изнутри</h2>
        <div class="cta__actions">
          <template v-if="auth.isAuthenticated">
            <AppButton :to="auth.homePath" variant="inverse" size="lg">Перейти в кабинет</AppButton>
          </template>
          <template v-else-if="DEMO_MODE">
            <AppButton variant="inverse" size="lg" :loading="demoLoading === 'candidate'" :disabled="demoLoading !== null" @click="enterDemo('candidate')">
              Демо: соискатель
            </AppButton>
            <AppButton variant="outline-inverse" size="lg" :loading="demoLoading === 'employer'" :disabled="demoLoading !== null" @click="enterDemo('employer')">
              Демо: работодатель
            </AppButton>
          </template>
          <template v-else>
            <AppButton :to="{ name: 'register' }" variant="inverse" size="lg">Создать аккаунт</AppButton>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ---------- Hero ---------- */
.hero {
  position: relative;
  overflow: hidden;
  background: var(--c-ink);
  color: var(--c-on-ink);
}
.hero::before {
  /* soft brand glow */
  content: '';
  position: absolute;
  inset: -20% -10% auto auto;
  width: 640px;
  height: 640px;
  background: radial-gradient(closest-side, rgba(64, 47, 255, 0.42), rgba(64, 47, 255, 0));
  pointer-events: none;
}
.hero::after {
  /* faint grid */
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(to bottom, #000 30%, transparent);
  pointer-events: none;
}
.hero__inner {
  position: relative;
  z-index: 1;
  display: grid;
  gap: var(--sp-10);
  padding-block: var(--sp-12) var(--sp-16);
}
.hero__copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-5);
}
.hero__eyebrow {
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #a9a3ff;
}
.hero__title {
  max-width: 18ch;
  font-size: var(--fs-3xl);
  line-height: 1.08;
  letter-spacing: -0.04em;
  color: #fff;
}
.hero__lead {
  max-width: 56ch;
  font-size: var(--fs-md);
  line-height: 1.6;
  color: var(--c-on-ink-muted);
}
.hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
  margin-top: var(--sp-2);
}
.hero__fine {
  font-size: var(--fs-sm);
  color: var(--c-on-ink-muted);
}
.hero__fine a {
  color: #c9c5ff;
}
.hero__fine a:hover {
  color: #fff;
}
.hero a:focus-visible,
.hero button:focus-visible {
  outline-color: #fff;
}

@media (min-width: 640px) {
  .hero__actions :deep(.btn) {
    min-width: 0;
  }
}
@media (max-width: 639px) {
  .hero__actions {
    width: 100%;
    flex-direction: column;
  }
  .hero__actions :deep(.btn) {
    width: 100%;
  }
}
@media (min-width: 1000px) {
  .hero__inner {
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
    align-items: center;
    gap: var(--sp-16);
    padding-block: var(--sp-20);
  }
}

/* Sample card */
.sample {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-6);
  border-radius: var(--r-xl);
  background: var(--c-surface);
  color: var(--c-text);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35);
}
@media (min-width: 1000px) {
  .sample {
    transform: rotate(1.2deg);
  }
}
.sample__tag {
  align-self: flex-start;
  padding: 3px 10px;
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-neutral-text);
}
.sample__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
}
.sample__name {
  font-family: var(--font-mono);
  font-size: var(--fs-xl);
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--c-ink);
}
.sample__city {
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.sample__cat {
  font-family: var(--font-mono);
  font-size: var(--fs-lg);
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--c-primary);
}
.sample__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.sample__facts {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: var(--fs-sm);
}
.sample__facts li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.sample__facts :deep(svg) {
  margin-top: 3px;
  color: var(--c-success-text);
}
.sample__foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-3);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border);
  font-size: var(--fs-sm);
  color: var(--c-text-muted);
}
.sample__foot strong {
  font-size: var(--fs-lg);
  color: var(--c-ink);
}

/* ---------- Sections ---------- */
.section {
  padding-block: var(--sp-12);
}
.section--alt {
  background: var(--c-surface);
  border-block: 1px solid var(--c-border);
}
@media (min-width: 768px) {
  .section {
    padding-block: var(--sp-20);
  }
}
.section__head {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.section__title {
  max-width: 24ch;
  font-size: clamp(1.5rem, 1.1rem + 1.8vw, 2.25rem);
  letter-spacing: -0.035em;
}

.sides {
  align-items: stretch;
}
.side {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}
.side__title {
  font-size: var(--fs-lg);
}
.steps {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}
.step {
  display: flex;
  gap: var(--sp-4);
}
.step__num {
  flex: none;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-weight: 700;
}
.step__title {
  font-family: var(--font-sans);
  font-size: var(--fs-base);
  font-weight: 600;
  letter-spacing: 0;
  margin-bottom: 2px;
}
.step__text {
  color: var(--c-text-muted);
  line-height: 1.55;
}

.source {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-3);
}
.source__title {
  font-size: var(--fs-md);
}
.source__text {
  flex: 1;
  font-size: var(--fs-sm);
  line-height: 1.55;
  color: var(--c-text-muted);
}
.source__weight {
  display: flex;
  width: 100%;
  align-items: baseline;
  justify-content: space-between;
  font-size: var(--fs-xs);
  color: var(--c-text-muted);
}
.source__weight-value {
  font-size: var(--fs-xl);
  font-weight: 700;
  color: var(--c-ink);
}
.source__bar {
  width: 100%;
  height: 6px;
  border-radius: var(--r-pill);
  background: var(--c-neutral-soft);
  overflow: hidden;
}
.source__bar-fill {
  display: block;
  height: 100%;
  border-radius: var(--r-pill);
  background: var(--c-primary);
}

.principle {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.principle__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin-bottom: var(--sp-2);
  border-radius: 12px;
  background: var(--c-ink);
  color: #fff;
}
.principle__title {
  font-size: var(--fs-md);
}
.principle__text {
  color: var(--c-text-muted);
  line-height: 1.55;
}

.honesty {
  padding: var(--sp-5);
  font-size: var(--fs-base);
  line-height: 1.6;
  color: var(--c-ink);
}
.honesty :deep(svg) {
  margin-top: 3px;
  color: var(--c-primary);
}
.honesty__title {
  margin-bottom: 4px;
  font-family: var(--font-mono);
  font-weight: 600;
}

/* ---------- Final call ---------- */
.cta {
  background: var(--c-primary);
  color: #fff;
}
.cta__inner {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-6);
  padding-block: var(--sp-12);
}
.cta__title {
  max-width: 22ch;
  font-size: clamp(1.5rem, 1.1rem + 1.8vw, 2.25rem);
  letter-spacing: -0.035em;
  color: #fff;
}
.cta__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}
.cta a:focus-visible,
.cta button:focus-visible {
  outline-color: #fff;
}
@media (min-width: 768px) {
  .cta__inner {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding-block: var(--sp-16);
  }
}
@media (max-width: 639px) {
  .cta__actions {
    width: 100%;
    flex-direction: column;
  }
  .cta__actions :deep(.btn) {
    width: 100%;
  }
}
</style>
