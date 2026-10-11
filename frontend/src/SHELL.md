# Памятка по каркасу фронтенда

Для тех, кто пишет страницы кабинетов (`pages/candidate/**`, `pages/employer/**`).
Здесь всё, чем можно пользоваться, не читая код каркаса. Источник типов и маршрутов —
`docs/API_CONTRACT.md`; типы лежат в `src/api/types.ts` (имена и поля один в один).

Правила: только `type` (без `interface` и `enum`), без `any` и `@ts-ignore`, импорт через
алиас `@/…`, тексты интерфейса по-русски, код и комментарии по-английски.

## 1. Как устроена страница

Страница рендерится внутри `CabinetLayout` в `<main class="container page">`. Это колонка с
отступами между детьми, поэтому страница может быть фрагментом (несколько корневых блоков) —
отступы между ними поставит `.page`. Внешний контейнер и шапку добавлять не нужно.

Типовая страница:

```vue
<script setup lang="ts">
import { getProfile } from '@/api/candidate'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useLoader } from '@/composables/useLoader'

const { data: profile, status, errorMessage, load } = useLoader(() => getProfile())
</script>

<template>
  <PageHeader title="Обзор" eyebrow="Соискатель" />
  <StateBlock v-if="status === 'loading'" state="loading" />
  <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />
  <template v-else-if="profile">…</template>
</template>
```

- Пустой список: `<StateBlock state="empty" title="…" text="…"><template #action>…</template></StateBlock>`.
- Ошибка действия (кнопка, форма) — тост: `toast.fromError(err)` (берёт `message` из ответа).
- Пока идёт запрос действия — `:loading="busy"` на `AppButton`.
- Страница пересоздаётся при смене `route.path` (а не query): для `/employer/candidates/:id`
  читайте `useRoute().params.id` при создании, фильтры поиска храните в `route.query` и
  меняйте через `router.replace({ query })` — страница при этом не перерисовывается целиком.
- Справочники к моменту показа страницы кабинета уже загружены (роутер ждёт `reference.load()`).
  Если сервер их не отдал, подписи берутся из статических таблиц, а списки навыков и городов пусты.
- Авторизация: токен подставляется автоматически; 401 на защищённом запросе выбрасывает
  пользователя на `/login`. Свою проверку ролей на страницах делать не нужно.

## 2. Компоненты (`@/components/…`)

Все `v-model` — через `defineModel`. «Модель» ниже — значение `v-model`.

### Формы

| Компонент | Пропсы | События / слоты |
| --- | --- | --- |
| `AppButton` | `variant`: `primary` (по умолч.) \| `secondary` \| `ghost` \| `danger` \| `inverse` \| `outline-inverse`; `size`: `sm` \| `md` (по умолч.) \| `lg`; `type` (`button` по умолч.); `loading`; `disabled`; `block`; `to` (маршрут — тогда это ссылка) | обычный `@click`; слот по умолчанию |
| `AppInput` | модель `string` (или `number \| null` при `type="number"`); `label`, `type`, `placeholder`, `hint`, `error`, `required`, `disabled`, `readonly`, `autocomplete`, `name`, `inputmode`, `maxlength`, `min`, `max`, `step`, `suffix` (единица справа, напр. `₽`) | `blur`, `enter`; `focus()` через ref |
| `AppSelect` | модель `T \| null` (`T` — `string` или `number`); `options: { value, label, disabled? }[]`; `label`, `placeholder` (добавляет пустой пункт, выбор даёт `null`), `hint`, `error`, `required`, `disabled`, `name` | — |
| `AppCheckbox` | модель `boolean`; `label` (или слот по умолчанию — для текста со ссылкой), `hint`, `error`, `disabled`, `required`, `name` | — |
| `AppTextarea` | модель `string`; `label`, `placeholder`, `hint`, `error`, `rows` (4), `maxlength` (включает счётчик), `required`, `disabled`, `name` | — |
| `ChipSelect` | модель `T[]`; `options`, `label`, `hint`, `error`, `single` (не больше одного), `disabled` | — |
| `SkillPicker` | модель `string[]` (id навыков); `label`, `placeholder`, `hint`, `error`, `exclude` (id, которые не предлагать), `disabled`, `maxSuggestions` (8). Поиск по справочнику навыков | — |
| `SegmentedControl` | модель `T`; `options`, `label`, `block` | — |

Модель `AppSelect` может быть `null`: поле формы объявляйте как `ref<Stack | null>(null)`.
`AppInput` определяет тип модели по `v-model`: для числового поля объявляйте `number | null`.
Пустую строку ошибки `error=""` компоненты считают «нет ошибки».

```vue
<AppInput v-model="form.salary" label="Зарплатные ожидания" type="number" suffix="₽" :error="errors.salary" />
<AppSelect v-model="form.stack" :options="reference.stackOptions" label="Стек" placeholder="Любой" />
<ChipSelect v-model="form.work_formats" :options="reference.workFormatOptions" label="Формат работы" />
```

### Окна и уведомления

| Компонент | Пропсы | События / слоты |
| --- | --- | --- |
| `AppModal` | модель `boolean` (открыто); `title`; `size`: `sm` \| `md` \| `lg`; `closable` (false — нельзя закрыть Esc/фоном/крестиком, пока идёт запрос) | `close`; слоты: по умолчанию, `footer` (кнопки) |
| `ConfirmModal` | модель `boolean`; `title`, `message`, `confirmLabel`, `cancelLabel`, `danger`, `loading`, `confirmDisabled` | `confirm` (сам не закрывается: закройте после запроса); слот по умолчанию — доп. содержимое (поле комментария) |
| `AppToasts` | — (уже подключён в `App.vue`) | тосты пушатся через `useToastStore()` |

```vue
<ConfirmModal v-model="askUnlink" title="Отвязать ФСП?" message="Результаты из реестра исчезнут из профиля."
  confirm-label="Отвязать" danger :loading="busy" @confirm="unlink" />

<AppModal v-model="creating" title="Новая вакансия" size="lg" :closable="!busy">
  <AppInput v-model="form.title" label="Название" required />
  <template #footer>
    <AppButton variant="ghost" :disabled="busy" @click="creating = false">Отмена</AppButton>
    <AppButton :loading="busy" @click="save">Сохранить</AppButton>
  </template>
</AppModal>
```

### Каркас страницы и состояния

| Компонент | Пропсы | События / слоты |
| --- | --- | --- |
| `PageHeader` | `title`, `subtitle`, `eyebrow` | слоты: `actions` (кнопки справа), по умолчанию (под подзаголовком) |
| `StatTile` | `label`, `value` (`string \| number`), `hint`, `tone`: `default` \| `primary` \| `success` \| `warning` | слот по умолчанию |
| `StateBlock` | `state`: `loading` \| `empty` \| `error`; `title`; `text` (для `error` — сообщение сервера); `retryLabel` («Повторить»); `compact` (без рамки, для карточек) | `retry`; слот `action` (для `empty`) |

```vue
<PageHeader title="Вакансии" subtitle="Что вы ищете сейчас" eyebrow="Работодатель">
  <template #actions><AppButton @click="creating = true">Новая вакансия</AppButton></template>
</PageHeader>
<div class="grid-3">
  <StatTile label="Кандидатов в выдаче" :value="total" hint="по текущим фильтрам" tone="primary" />
  <StatTile label="Активных вакансий" :value="active" />
</div>
<StateBlock state="empty" title="Вакансий пока нет" text="Создайте первую, чтобы отправлять офферы.">
  <template #action><AppButton @click="creating = true">Создать вакансию</AppButton></template>
</StateBlock>
```

### Профиль, категория, доверие

| Компонент | Пропсы | События / слоты |
| --- | --- | --- |
| `SourceBadge` | `verification: Verification`; `size`: `sm` \| `md`. «Подтверждено ФСП» (заливка, в режиме `mock` с меткой «демо»), «Подтверждено тестом» (зелёный), «Из резюме» (серый), «Заявлено» (контур) | — |
| `SkillChip` | `title`; `verification` (цвет точки); `evidence` 0..1 (сила, три ступени); `missing` (пунктирный «нет у кандидата») | — |
| `CategoryCard` | `category: Category`; `title` («Категория»); `showSkills` (чипы `top_skills`). Четыре ячейки: стек, грейд, роль, формат; пометки «стек не подтверждён» / «грейд не подтверждён»; `grade_note`; при `stack = null` — «Категория не определена» | слоты: `undetermined` (призыв к действию), `footer` |
| `GradeExplanation` | `category`; `title`; `v-model:open` или просто `open` (начальное состояние). Строки `grade_explanations` с полосками, отрицательные (потолки) красные, итог = `grade_points`, шкала порогов | — |
| `ConfidenceMeter` | `category` (нужны `confidence_index` и `confidence_breakdown`); `title` | — |
| `FactList` | `facts`; `kinds` (какие группы и в каком порядке; по умолч. достижения, разряды, навыки, опыт, роли); `removable` (кнопка «Удалить» у достижений, добавленных вручную); `emptyText` | `remove(fact)` — запрос делает страница |
| `ScoreRing` | `value: number \| null` (`null` — прочерк); `size` (px, 72); `caption` | — |
| `MoneyRange` | `amount` (одна сумма) или `from`/`to` (вилка: «от», «до», «a – b»); `size`: `sm` \| `md` \| `lg` \| `xl`; `emptyText` | — |
| `AppIcon` | `name`: `check` `x` `plus` `chevron-down` `chevron-right` `arrow-right` `alert` `info` `lock` `shield` `trash` `external` `search` `user` `filter` `logout` `spark`; `size` (18) | — |

```vue
<CategoryCard :category="profile.category" title="Ваша категория" show-skills>
  <template #undetermined><AppButton :to="{ name: 'candidate-fsp' }">Привязать ФСП</AppButton></template>
</CategoryCard>
<GradeExplanation :category="profile.category" open />
<ConfidenceMeter :category="profile.category" />
<FactList :facts="profile.facts" :kinds="['achievement']" removable @remove="onRemove" />
<SourceBadge :verification="fact.verification" size="sm" />
<SkillChip :title="skill.title" :verification="skill.verification" :evidence="skill.evidence" />
<SkillChip title="Docker" missing />
<ScoreRing :value="match.score" caption="из 100" />
<MoneyRange :from="vacancy.salary_from" :to="vacancy.salary_to" />
<MoneyRange :amount="offer.salary" size="lg" />
<AppIcon name="check" :size="16" />
```

Служебные (на страницах не нужны): `AppLogo`, `DemoBanner`, `AuthCard`.

## 3. API (`@/api/…`)

Каждая функция возвращает `Promise` с типом ответа из контракта и бросает `ApiRequestError`.

`client.ts`:

- `ApiRequestError` — поля `status` (0 — сеть), `error_code`, `message` (по-русски, можно показывать), `details`, `trace_id`.
- `getErrorMessage(err, fallback?)`, `hasErrorCode(err, 'FSP_ALREADY_LINKED')`, `isApiRequestError(err)`.
- `fieldErrors(err)` → `Record<поле, текст>` для `VALIDATION_ERROR` (поддерживает несколько форм `details`).
- `serverNow()` — время сервера в мс (по заголовку `Date`): для таймера теста вместо `Date.now()`.
- `apiRequest`, `http` — низкоуровневые, на страницах обычно не нужны.

`candidate.ts` (все — для роли `candidate`):

| Функция | Запрос | Ответ |
| --- | --- | --- |
| `getProfile()` | `GET /candidate/profile` | `CandidateProfile` |
| `patchProfile(patch: ProfilePatch)` | `PATCH /candidate/profile` | `CandidateProfile` |
| `linkFsp(fspId)` | `POST /candidate/fsp/link` | `FspLinkResult` |
| `unlinkFsp()` | `DELETE /candidate/fsp/link` | `CandidateProfile` |
| `uploadResume({ file } \| { text })` | `POST /candidate/resume` (multipart) | `ResumeParseResult` |
| `deleteResume()` | `DELETE /candidate/resume` | `CandidateProfile` |
| `getDemoResume()` | `GET /candidate/resume/demo` | `{ text }` |
| `listTests()` | `GET /candidate/tests` | `TestInfo[]` |
| `startTest(skill)` | `POST /candidate/tests/{skill}/start` | `TestSession` |
| `submitTest(sessionId, { answers })` | `POST /candidate/tests/sessions/{id}/submit` | `TestResult` |
| `addAchievement(input)` | `POST /candidate/achievements` | `CandidateProfile` |
| `deleteAchievement(factId)` | `DELETE /candidate/achievements/{id}` | `CandidateProfile` |
| `listOffers()` | `GET /candidate/offers` | `CandidateOffer[]` |
| `respondToOffer(id, { decision, comment? })` | `POST /candidate/offers/{id}/respond` | `CandidateOffer` |

`employer.ts` (для роли `employer`):

| Функция | Запрос | Ответ |
| --- | --- | --- |
| `getEmployerProfile()` | `GET /employer/profile` | `EmployerProfile` |
| `getCategoryMatrix({ team_role?, work_format? })` | `GET /employer/categories` | `CategoryMatrix` |
| `searchCandidates(query: MatchQuery)` | `POST /employer/search` | `SearchResponse` |
| `getCandidate(id)` | `GET /employer/candidates/{id}` | `CandidateCard` |
| `listVacancies()` | `GET /employer/vacancies` | `Vacancy[]` |
| `createVacancy(input: VacancyInput)` | `POST /employer/vacancies` | `Vacancy` |
| `updateVacancy(id, patch)` | `PATCH /employer/vacancies/{id}` | `Vacancy` |
| `createOffer({ candidate_id, vacancy_id, salary, message? })` | `POST /employer/offers` | `EmployerOffer` |
| `listEmployerOffers()` | `GET /employer/offers` | `EmployerOffer[]` |

`reference.ts`: `getDictionaries()`, `getHealth()`, `getFspAthlete(fspId)` (мок реестра). `auth.ts`: `login`, `register`, `fetchMe`
(на страницах кабинетов пользуйтесь хранилищем `auth`).

Нюансы контракта, которые легко забыть: `ProfilePatch` с `full_name`/`birth_date` при привязанном ФСП даёт
`FSP_LINKED_LOCKED`; `DELETE /candidate/achievements/{id}` работает только для фактов с `source = 'self'`;
в `submitTest` индекс ответа — позиция варианта в том порядке, в котором варианты пришли клиенту.
Любое действие, вернувшее `profile`/`CandidateProfile`, — повод обновить локальные данные без перезагрузки.

## 4. Хранилища (Pinia, `@/stores/…`)

`useAuthStore()` — `user`, `isAuthenticated`, `role`, `homePath`, `displayName`; методы `login(body)`,
`register(body)`, `demoLogin(role)`, `logout()`, `restore()`, `setUser(user)`.

`useReferenceStore()` — загружается один раз (`load()` не бросает, `status`: `idle|loading|ready|error`).
- `dictionaries`, `registryMode`, `isMock`.
- Подписи по id (безопасны и до загрузки): `stackTitle`, `gradeTitle`, `teamRoleTitle`, `workFormatTitle`,
  `skillTitle`, `disciplineTitle`, `levelTitle` (уровень соревнования), `rankTitle` (разряд),
  `sourceTitle`, `verificationTitle`; `joinTitles(ids, titleFn)` — «Удалённо, Гибрид».
- Списки для выбора `{ value, label }`: `stackOptions`, `gradeOptions`, `teamRoleOptions`, `workFormatOptions`,
  `disciplineOptions`, `levelOptions`, `rankOptions`, `skillOptions`, `cityOptions`; `cities: string[]`.

`useToastStore()` — `success(msg)`, `info(msg)`, `error(msg)`, `fromError(err, fallback?)`, `dismiss(id)`.

`useInboxStore()` — счётчик офферов соискателя, ждущих ответа (бейдж на вкладке «Офферы»):
`pendingOffers`, `refresh()`, `setPending(n)`. Страница офферов после ответа вызывает `refresh()`.

Композабл `useLoader(fetcher, { immediate? })` → `{ data, status, errorMessage, load, setData }`;
`status`: `idle|loading|ready|error` (ложится на `StateBlock`). `data` — `shallowRef`: заменяйте значение
целиком (`setData(profile)`), не меняйте поля.

## 5. Утилиты (`@/utils/…`)

`format.ts`: `formatMoney(120000)` → «120 000 ₽»; `formatMoneyRange(from, to)`; `formatNumber`; `formatDecimal`;
`formatScore(46.8)` → «46,8»; `formatPoints(-8)` → «−8,0»; `formatPercent(0.26)` → «26%»;
`formatYears(1.5)` → «1,5 года»; `plural(n, ['год', 'года', 'лет'])` (только слово); `formatCount(3, [...])` → «3 года»;
`formatDate('2026-05-14')` → «14 мая 2026»; `formatDayMonth`; `formatShortDate`; `formatDateTime`;
`formatTimeLeft(isoOrDate, nowMs?)` → «2 ч 10 мин» / «сейчас»; `formatAgo(iso)` → «5 мин назад»;
`formatCountdown(seconds)` → «7:32»; `parseServerDate(iso)` (дата без часового пояса считается UTC).

`labels.ts`: статические подписи и порядок справочников (`STACK_TITLES`, `GRADE_TITLES`, `STACK_ORDER`, …),
`ACHIEVEMENT_RESULT_TITLES`, `OFFER_STATUS_TITLES` («Ждёт ответа» / «Принят» / «Отклонён»), `QUIZ_LEVEL_TITLES`,
`VERIFICATION_WEIGHTS`, `optionsFrom(order, titles)`.

`facts.ts`: безопасное чтение `Fact.value` — `skillFactValue`, `experienceFactValue`, `achievementFactValue`,
`rankFactValue`, `roleFactValue`, `achievementYear(fact)`, `isManualAchievement(fact)`, `isHttpUrl(url)`
(для `href`: пускайте в ссылку только http/https).

`demo.ts`: `DEMO_MODE`, `demoAccount(role)`, `DEMO_FSP_ID` (`FSP-2024-00117` — подсказка на странице ФСП).

## 6. Маршруты

Имена: `landing`, `login`, `register`, `privacy`, `candidate-overview` (`/candidate`), `candidate-profile`,
`candidate-fsp`, `candidate-tests`, `candidate-offers`, `employer-dashboard` (`/employer`), `employer-search`,
`employer-candidate` (`/employer/candidates/:id`, `id` — число), `employer-vacancies`, `employer-offers`, `not-found`.

Ссылка в поиск с фильтром: `{ name: 'employer-search', query: { stacks: 'backend', grades: 'junior' } }`
(формат query — на совести страницы поиска). Гость на защищённой странице попадает на `/login?redirect=…`,
чужая роль — в свой кабинет.

## 7. CSS (`styles/tokens.css`, `styles/base.css`)

Переменные:
- Цвет: `--c-primary` (#402FFF), `--c-primary-hover`, `--c-primary-soft`, `--c-primary-soft-2`, `--c-ink` / `--c-ink-2` (тёмный),
  `--c-bg` (фон), `--c-surface` (карточка), `--c-border`, `--c-border-strong`, `--c-text`, `--c-text-muted` (вторичный
  текст, контраст ≥ AA), `--c-placeholder` (#6B6C73, 5,2:1 на белом, ≥ AA — плейсхолдеры и третичный текст, класс
  `.faint`), `--c-text-faint` (#9B9C9E, 2,75:1 — только декор: точки, разделители; никогда для текста и плейсхолдеров).
- Статусы: `--c-danger` (заливки, рамки) и `--c-danger-text` (текст, AA); `--c-success` / `--c-success-text`;
  `--c-warning-text`; каждый статус имеет `-soft` и `-border`.
- Шрифты: `--font-sans` (Inter), `--font-mono` (JetBrains Mono — заголовки и цифры). Размеры: `--fs-xs` … `--fs-3xl`.
- Отступы `--sp-1` … `--sp-20` (шаг 4 px), радиусы `--r-sm|md|lg|xl|pill`, тени `--shadow-sm|md|lg`, `--ring` (фокус),
  `--ease`, `--t-fast`, `--t-base`, ширины `--content-w`, `--narrow-w`, `--gutter`.

Вспомогательные классы:
- Раскладка: `.container`, `.container--narrow`, `.page`, `.stack` / `.stack-sm` / `.stack-lg` (колонка с зазором),
  `.row` (ряд с переносом; `.row--between`, `.row--end`, `.row--nowrap`), `.grid-2`, `.grid-3`, `.grid-4`
  (адаптивные сетки: на телефоне одна колонка), `.scroll-x`.
- Поверхности: `.card` (`--lg`, `--flat`, `--interactive`), `.callout` (`--warning`, `--danger`, `--success`, `--primary`).
- Текст: `.mono`, `.num` (моноширинные цифры), `.muted`, `.faint`, `.text-sm`, `.text-xs`, `.text-danger`,
  `.text-success`, `.text-primary`, `.lead`, `.eyebrow`, `.h1` / `.h2` / `.h3`, `.link`, `.truncate`, `.nowrap`,
  `.section-title` (заголовок группы с линией), `.sr-only`.
- Поля формы (общие для `App*` компонентов): `.field`, `.field__label`, `.field__control`, `.field__hint`,
  `.field__error`, `.field--error`.
- Переходы: `fade`, `slide-down` (для `<Transition name="…">`).

Вёрстка от 375 px: страницы не должны давать горизонтальный скролл; сетки — на `.grid-*` или `auto-fit/minmax`.
Числа и идентификаторы — классом `.num`/`.mono`. Подтверждённое от неподтверждённого отличайте бейджем, а не только цветом.
