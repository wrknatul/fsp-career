<script setup lang="ts">
import { RouterLink } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'

type VisibilityRow = { what: string; before: string; after: string; tone: 'open' | 'closed' | 'masked' }

// What an employer sees (SPEC section 8, "Приватность до принятого оффера").
const visibility: VisibilityRow[] = [
  { what: 'Имя', before: '«Алексей С.»: имя и первая буква фамилии', after: 'Полное ФИО', tone: 'masked' },
  {
    what: 'Категория, навыки, достижения, источники подтверждения',
    before: 'Видит',
    after: 'Видит',
    tone: 'open',
  },
  {
    what: 'Текст «о себе» и подписи к фактам',
    before: 'Видит, но почта, телефон, @ники и ссылки в тексте заменяются на «[скрыто]»',
    after: 'Без замены: текст виден как есть',
    tone: 'masked',
  },
  { what: 'Почта, телефон, Telegram', before: 'Не видит', after: 'Видит', tone: 'masked' },
  { what: 'Дата рождения', before: 'Не видит', after: 'Не видит никогда', tone: 'closed' },
  { what: 'Текст резюме и файл', before: 'Не видит', after: 'Не видит никогда', tone: 'closed' },
]
</script>

<template>
  <article class="privacy">
    <div class="container container--narrow privacy__inner">
      <header class="privacy__head">
        <p class="eyebrow">Приватность</p>
        <h1 class="privacy__title">Какие данные мы собираем и кто их видит</h1>
        <p class="lead">
          Без юридических формулировок: что мы храним, зачем, что видит работодатель и в какой момент, как скрыть
          профиль и убрать данные.
        </p>
      </header>

      <div class="callout callout--primary" role="note">
        <AppIcon name="info" :size="18" />
        <p>
          Это прототип для хакатона. Реестр ФСП в нём смоделирован, а данные живут в базе стенда. Для проверки
          используйте демо-аккаунты или вымышленные данные.
        </p>
      </div>

      <section class="block">
        <h2 class="block__title">Что мы собираем</h2>
        <div class="grid-2">
          <div class="card card--flat">
            <h3 class="block__sub">Соискатель</h3>
            <ul class="list">
              <li><strong>Аккаунт:</strong> почта, ФИО и пароль. Пароль хранится только в виде хеша, открытым текстом его нет нигде.</li>
              <li>
                <strong>Анкета:</strong> дата рождения, город, форматы работы, готовность к переезду, зарплатные
                ожидания, «о себе», Telegram и телефон.
              </li>
              <li><strong>Резюме:</strong> текст и название файла. Из него мы достаём навыки и опыт.</li>
              <li><strong>ФСП:</strong> ФСП ID, результаты соревнований и спортивные разряды из реестра.</li>
              <li><strong>Тесты:</strong> ответы на вопросы экспресс-проверки и результат.</li>
              <li><strong>Достижения вручную:</strong> то, что вы вписали сами.</li>
            </ul>
          </div>
          <div class="card card--flat">
            <h3 class="block__sub">Работодатель</h3>
            <ul class="list">
              <li><strong>Аккаунт:</strong> почта, имя контактного лица, пароль (в виде хеша).</li>
              <li><strong>Компания:</strong> название и контакты для кандидатов.</li>
              <li><strong>Вакансии и офферы:</strong> то, что вы создали и отправили.</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="block">
        <h2 class="block__title">Зачем это нужно</h2>
        <ul class="list">
          <li>Чтобы определить вашу категорию: стек, грейд, роль в команде и формат работы.</li>
          <li>Чтобы работодатель мог найти категорию и отправить вам оффер с зарплатой.</li>
          <li>
            Чтобы подтвердить факты. ФИО и дата рождения нужны для сверки с реестром ФСП: привязка проходит, только
            если они совпали. Больше нигде дата рождения не используется и работодателю не показывается.
          </li>
        </ul>
      </section>

      <section class="block">
        <h2 class="block__title">Кто видит ваш профиль и когда</h2>
        <p class="block__text">
          Работодатель видит вас, только если включено «Показывать профиль работодателям». До принятого вами оффера
          он знает о вас ровно столько, сколько в левой колонке. Если вы отклонили оффер, ничего не меняется:
          работодатель по-прежнему видит только «Алексей С.».
        </p>

        <div class="vis" role="table" aria-label="Что видит работодатель">
          <div class="vis__row vis__row--head" role="row">
            <span role="columnheader">Данные</span>
            <span role="columnheader">До принятого оффера</span>
            <span role="columnheader">После принятого оффера</span>
          </div>
          <div v-for="row in visibility" :key="row.what" class="vis__row" role="row">
            <span class="vis__what" role="cell">{{ row.what }}</span>
            <span class="vis__cell" data-label="До принятого оффера" role="cell">{{ row.before }}</span>
            <span class="vis__cell" :class="`vis__cell--${row.tone}`" data-label="После принятого оффера" role="cell">
              {{ row.after }}
            </span>
          </div>
        </div>

        <p class="block__text">
          Контакты открываются только вашим решением: нажмите «Принять» у конкретного оффера, и именно эта компания
          получит почту, телефон, Telegram и полное имя. Другим работодателям они по-прежнему закрыты.
        </p>
      </section>

      <section class="block">
        <h2 class="block__title">Чего мы не делаем</h2>
        <ul class="list">
          <li>
            Не отправляем ваши данные во внешние сервисы. Резюме разбирается правилами на нашем сервере, а
            сходство с запросом считается локально: нейросетей третьих сторон здесь нет.
          </li>
          <li>Не собираем данные с чужих сайтов и не показываем чужие вакансии. Вакансии заводят только работодатели.</li>
          <li>Не показываем работодателю контакты и дату рождения без вашего решения.</li>
        </ul>
      </section>

      <section class="block">
        <h2 class="block__title">Как скрыть профиль и убрать данные</h2>
        <ol class="list list--numbered">
          <li>
            <strong>Скрыть профиль.</strong> На странице «Обзор» выключите «Показывать профиль работодателям». Вы
            сразу пропадёте из поиска и с витрины категорий.
          </li>
          <li>
            <strong>Убрать источники.</strong> Отвяжите ФСП (результаты из реестра удалятся), удалите резюме (вместе
            с текстом и найденными фактами) и достижения, которые добавили вручную.
          </li>
          <li><strong>Отказаться от оффера.</strong> Нажмите «Отклонить»: контакты останутся закрытыми.</li>
        </ol>
        <div class="callout callout--warning" role="note">
          <AppIcon name="alert" :size="18" />
          <p>
            Полного удаления аккаунта в этой версии нет — это известное ограничение прототипа, мы его не скрываем.
            Контакты, которые вы открыли принятием оффера, уже у работодателя: задним числом их не отозвать.
          </p>
        </div>
      </section>

      <section class="block">
        <h2 class="block__title">Реестр ФСП в демо</h2>
        <p class="block__text">
          Доступа к настоящему реестру у нас нет, поэтому спортсмены, соревнования и протоколы в стенде вымышлены.
          В рабочей версии привязка пройдёт через аккаунт ФСП, с вашего явного согласия.
        </p>
      </section>

      <p class="privacy__back">
        <RouterLink :to="{ name: 'landing' }" class="link">← На главную</RouterLink>
      </p>
    </div>
  </article>
</template>

<style scoped>
.privacy {
  padding-block: var(--sp-8) var(--sp-16);
}
@media (min-width: 768px) {
  .privacy {
    padding-block: var(--sp-16) var(--sp-20);
  }
}
.privacy__inner {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
}
.privacy__head {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.privacy__title {
  font-size: clamp(1.75rem, 1.3rem + 2vw, 2.5rem);
  letter-spacing: -0.035em;
}
.block {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.block__title {
  font-size: var(--fs-xl);
}
.block__sub {
  margin-bottom: var(--sp-3);
  font-size: var(--fs-md);
}
.block__text {
  line-height: 1.65;
  color: var(--c-text-muted);
}
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding-left: 1.25em;
  line-height: 1.6;
  color: var(--c-text-muted);
}
.list strong {
  color: var(--c-ink);
}
.list--numbered {
  list-style: decimal;
}
.list li::marker {
  color: var(--c-primary);
  font-weight: 700;
}

.callout p {
  line-height: 1.55;
}
.callout :deep(svg) {
  margin-top: 2px;
}

/* Visibility table: rows on desktop, cards on phones. */
.vis {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  overflow: hidden;
}
.vis__row {
  display: grid;
  gap: var(--sp-1);
  padding: var(--sp-4);
  border-bottom: 1px solid var(--c-border);
}
.vis__row:last-child {
  border-bottom: 0;
}
.vis__row--head {
  display: none;
}
.vis__what {
  font-weight: 600;
  color: var(--c-ink);
}
.vis__cell {
  font-size: var(--fs-sm);
  line-height: 1.5;
  color: var(--c-text-muted);
}
.vis__cell::before {
  content: attr(data-label) ': ';
  font-weight: 600;
  color: var(--c-text);
}
.vis__cell--closed {
  color: var(--c-danger-text);
  font-weight: 600;
}
.vis__cell--open {
  color: var(--c-success-text);
}
@media (min-width: 768px) {
  .vis__row {
    grid-template-columns: 1.1fr 1.4fr 1fr;
    gap: var(--sp-5);
    align-items: start;
  }
  .vis__row--head {
    display: grid;
    background: var(--c-surface-2);
    font-size: var(--fs-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--c-text-muted);
  }
  .vis__cell::before {
    content: none;
  }
}
.privacy__back {
  padding-top: var(--sp-4);
}
</style>
