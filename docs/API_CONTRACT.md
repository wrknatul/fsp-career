# ФСП.Карьера — контракт API v1 (редакция 2)

Базовый путь: `/api/v1`. Формат — JSON, кроме загрузки резюме (multipart).
Авторизация: `Authorization: Bearer <access_token>`. Даты — ISO 8601, время в UTC.

Бэкенд описывает эти структуры pydantic-моделями в `app/schemas/**` (имена
классов равны именам типов), фронтенд — типами в `frontend/src/api/types.ts`.
Имена полей и значения литералов совпадают буква в букву.

## Ошибки

Любой ответ 4xx/5xx:

```ts
type ApiError = {
  success: false
  error_code: string        // UPPER_SNAKE_CASE
  message: string           // по-русски, можно показывать пользователю
  trace_id: string
  details: Record<string, unknown>
}
```

| Код | HTTP | Когда |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | тело или параметры не прошли проверку; неизвестный id навыка |
| `UNAUTHORIZED` | 401 | нет токена, токен неверный или истёк |
| `FORBIDDEN` | 403 | роль не подходит |
| `NOT_FOUND` | 404 | объекта нет, он чужой или кандидат скрыт |
| `INVALID_CREDENTIALS` | 401 | неверная почта или пароль |
| `EMAIL_TAKEN` | 409 | почта уже зарегистрирована |
| `CONSENT_REQUIRED` | 422 | `consent` не `true` |
| `PROFILE_INCOMPLETE` | 409 | для привязки ФСП нужны ФИО и дата рождения |
| `RATE_LIMITED` | 429 | больше 5 попыток привязки ФСП за час; `details.limit`, `details.available_at` |
| `FSP_ATHLETE_NOT_FOUND` | 404 | |
| `FSP_ALREADY_LINKED` | 409 | `details.linked_to_you: boolean` |
| `FSP_IDENTITY_MISMATCH` | 409 | |
| `FSP_LINKED_LOCKED` | 409 | смена ФИО или даты рождения при привязанном ФСП |
| `RESUME_EMPTY` | 422 | нет ни файла, ни текста, либо текст пуст |
| `UNSUPPORTED_FILE` | 415 | не `.txt`/`.pdf`, PDF не читается или длиннее 20 страниц |
| `FILE_TOO_LARGE` | 413 | файл больше 2 МБ или текст из файла длиннее 100 000 символов |
| `TEST_NOT_FOUND` | 404 | нет такого теста или сессии |
| `TEST_COOLDOWN` | 409 | `details.available_at` |
| `TEST_SESSION_EXPIRED` | 409 | |
| `TEST_ALREADY_SUBMITTED` | 409 | |
| `VACANCY_INACTIVE` | 409 | оффер по неактивной вакансии |
| `OFFER_ALREADY_SENT` | 409 | |
| `OFFER_ALREADY_RESPONDED` | 409 | |
| `CONFLICT` | 409 | конфликт целостности данных, для которого нет отдельного кода |
| `FSP_REGISTRY_UNAVAILABLE` | 503 | реестр ФСП недоступен или отдал повреждённую запись |
| `BAD_REQUEST` | 400 | тело запроса не разобрать |
| `METHOD_NOT_ALLOWED` | 405 | |
| `INTERNAL_ERROR` | 500 | |

## Общие типы

```ts
type Role = 'candidate' | 'employer'
type Stack = 'backend' | 'frontend' | 'fullstack' | 'mobile' | 'ml' | 'devops' | 'security' | 'embedded' | 'qa' | 'analyst'
type Grade = 'intern' | 'junior' | 'middle' | 'senior'
type TeamRole = 'lead' | 'developer' | 'researcher' | 'devops' | 'qa' | 'analyst'
type WorkFormat = 'remote' | 'office' | 'hybrid'
type Source = 'fsp' | 'test' | 'resume' | 'self'
type Verification = 'verified' | 'tested' | 'parsed' | 'declared'
type FactKind = 'skill' | 'experience' | 'achievement' | 'rank' | 'role'
type Discipline = 'algorithmic' | 'product' | 'security' | 'robotics' | 'uav'
type CompetitionLevel = 'municipal' | 'regional' | 'district' | 'national' | 'international'
type SportRank = 'third' | 'second' | 'first' | 'kms' | 'ms'
type AchievementResult = 'winner' | 'prize' | 'participant'
type OfferStatus = 'sent' | 'accepted' | 'declined'

type User = { id: number; email: string; role: Role; full_name: string }

type Fact = {
  id: number
  kind: FactKind
  key: string                 // id навыка | 'total' | 'fsp:<id>' | 'manual:<uuid>' | 'sport_rank' | 'fsp_captain' | 'fsp_team:<role>' | 'resume_lead'
  title: string               // готовая подпись по-русски
  value: Record<string, unknown>
  source: Source
  verification: Verification
  evidence: string | null
  created_at: string
}
// value по видам:
//  skill:       { level: 1 | 2 | 3, score?: number }
//  experience:  { years: number, positions: { title: string, company: string | null, period: string, years: number }[] }
//  achievement: { title: string, discipline: Discipline | null, level: CompetitionLevel, place: number | null,
//                 result: AchievementResult, date: string | null, year: number | null,
//                 team_name: string | null, team_role: string | null, participants_total: number | null,
//                 document_url: string | null }
//  rank:        { rank: SportRank, discipline: Discipline | null, assigned_at: string | null, order_no: string | null }
//  role:        { reason: string }

type Explanation = { label: string; points: number; source: Source | null; verification: Verification | null }
type SkillEvidence = { skill: string; title: string; evidence: number; best_source: Source; verification: Verification }

type Category = {
  stack: Stack | null
  stack_confirmed: boolean            // у стека есть core-навык, подтверждённый ФСП или тестом
  grade: Grade | null                 // null, когда stack = null
  grade_confirmed: boolean            // есть хотя бы один факт verified или tested
  team_role: TeamRole | null
  team_role_source: Source | null     // 'resume' для lead, иначе null
  work_formats: WorkFormat[]
  label: string                       // 'Backend · Middle · Разработчик · Удалённо, гибрид' | 'Категория не определена'
  grade_points: number
  grade_explanations: Explanation[]   // вклады после потолков; сумма = grade_points
  grade_note: string | null
  experience_years: number
  experience_points: number
  achievement_points: number          // результаты ФСП + разряд, после потолков
  stack_scores: { stack: Stack; score: number }[]     // по убыванию, только > 0, без fullstack
  top_skills: SkillEvidence[]         // до 8, по убыванию evidence
  confidence_index: number            // 0..100
  confidence_breakdown: { label: string; points: number; max: number; done: boolean }[]
}
```

## Служебные

- `GET /health` → `{ status: 'ok', version: string, database: 'ok' | 'error' }`
- `GET /reference/dictionaries` (без авторизации) →

```ts
type Dictionaries = {
  stacks: { id: Stack; title: string }[]
  grades: { id: Grade; title: string }[]
  team_roles: { id: TeamRole; title: string }[]
  work_formats: { id: WorkFormat; title: string }[]
  sources: { id: Source; title: string }[]
  verifications: { id: Verification; title: string; weight: number }[]
  disciplines: { id: Discipline; title: string }[]
  competition_levels: { id: CompetitionLevel; title: string }[]
  sport_ranks: { id: SportRank; title: string }[]
  skills: { id: string; title: string; stacks: string[] }[]
  cities: string[]
  fsp_registry_mode: 'mock' | 'live'
}
```

## Авторизация

- `POST /auth/register` → 201 `{ access_token: string, token_type: 'bearer', user: User }`.
  Тело: `{ email, password (8–72 байта), role, full_name, consent: true,
  show_profile?: boolean (только candidate, по умолчанию false → visible),
  company_name?: string (обязателен для employer) }`
- `POST /auth/login` — `{ email, password }` → `{ access_token, token_type, user }`
- `GET /auth/me` → `User`

## Соискатель (роль `candidate`)

```ts
type CandidateProfile = {
  id: number
  user: User
  birth_date: string | null          // 'YYYY-MM-DD'
  city: string | null
  work_formats: WorkFormat[]
  relocation: boolean
  salary_expectation: number | null
  about: string | null
  telegram: string | null
  phone: string | null
  visible: boolean
  fsp: { fsp_id: string; linked_at: string; region: string | null } | null
  resume: { filename: string | null; parsed_at: string; parser: 'rules'; chars: number } | null
  category: Category
  facts: Fact[]
  updated_at: string
}
```

- `GET /candidate/profile` → `CandidateProfile`
- `PATCH /candidate/profile` — любые из
  `{ full_name, birth_date, city, work_formats, relocation, salary_expectation, about, telegram, phone, visible }`
  → `CandidateProfile`. `full_name`/`birth_date` при привязанном ФСП → `FSP_LINKED_LOCKED`.

### ФСП

```ts
type FspLinkResult = {
  athlete: { fsp_id: string; short_name: string; region: string | null }
  imported: { achievements: number; ranks: number; skills: number; roles: number }
  profile: CandidateProfile
}
```

- `POST /candidate/fsp/link` — `{ fsp_id: string }` → 200 `FspLinkResult`
- `DELETE /candidate/fsp/link` → `CandidateProfile`

### Резюме

- `POST /candidate/resume` — `multipart/form-data`: поле `file` (.txt/.pdf)
  **или** поле `text` → 200

```ts
type ResumeParseResult = {
  parser: 'rules'
  extracted: {
    skills: { skill: string; title: string; level: 1 | 2 }[]
    experience_years: number
    positions: { title: string; company: string | null; period: string; years: number; is_it: boolean }[]
    work_formats: WorkFormat[]
    city: string | null
    salary_expectation: number | null
    is_lead: boolean
  }
  applied_prefs: string[]            // какие пустые поля профиля заполнены из резюме
  profile: CandidateProfile
}
```

- `DELETE /candidate/resume` → `CandidateProfile`
- `GET /candidate/resume/demo` → `{ text: string }`

### Тесты

```ts
type TestInfo = {
  skill: string; title: string; description: string
  questions_per_session: number; time_limit_seconds: number
  best_result: { level: 1 | 2 | 3; level_title: string; score: number; submitted_at: string } | null
  active_session_id: number | null   // есть открытая неистёкшая сессия
  available_at: string | null        // не null, если действует пауза
}
type TestSession = {
  session_id: number; skill: string; title: string
  started_at: string; expires_at: string
  questions: { id: string; text: string; difficulty: 1 | 2 | 3; options: string[] }[]
}
type TestResult = {
  session_id: number; skill: string
  score: number                      // 0..1 — доля набранного веса
  level: 0 | 1 | 2 | 3
  passed: boolean
  correct: number; total: number
  level_title: string                // 'Не сдан' | 'Базовый' | 'Уверенный' | 'Продвинутый'
  profile: CandidateProfile
}
```

- `GET /candidate/tests` → `TestInfo[]`
- `POST /candidate/tests/{skill}/start` → 201 `TestSession` (или 200 с уже открытой сессией)
- `POST /candidate/tests/sessions/{session_id}/submit` —
  `{ answers: Record<string, number> }` (id вопроса → индекс варианта в том
  порядке, в котором варианты пришли клиенту) → `TestResult`

### Достижения вручную

- `POST /candidate/achievements` —
  `{ title (3–200), year (1990..текущий), level: CompetitionLevel, result: AchievementResult, discipline?: Discipline | null, document_url?: string | null }`
  → 201 `CandidateProfile`
- `DELETE /candidate/achievements/{fact_id}` → `CandidateProfile` (только свой факт с `source = self`, иначе `NOT_FOUND`)

### Офферы

```ts
type CandidateOffer = {
  id: number
  status: OfferStatus
  salary: number
  message: string | null
  created_at: string
  responded_at: string | null
  candidate_comment: string | null
  vacancy: { id: number; title: string; description: string; stack: Stack; grade: Grade; work_formats: WorkFormat[]; city: string | null; salary_from: number | null; salary_to: number | null }
  company: { name: string; about: string | null; website: string | null; verified: boolean }
  employer_contacts: { contact_name: string | null; contact_email: string | null; contact_telegram: string | null } | null   // только при accepted
}
```

- `GET /candidate/offers` → `CandidateOffer[]` (новые сверху)
- `POST /candidate/offers/{id}/respond` — `{ decision: 'accept' | 'decline', comment?: string (до 500) }` → `CandidateOffer`

## Работодатель (роль `employer`)

```ts
type EmployerProfile = { id: number; user: User; company_name: string; about: string | null; website: string | null; contact_name: string | null; contact_email: string | null; contact_telegram: string | null; verified: boolean }

type CategoryMatrix = {
  total_candidates: number
  cells: { stack: Stack; grade: Grade; count: number; fsp_verified: number }[]   // только count > 0
  by_stack: { stack: Stack; count: number }[]
  by_grade: { grade: Grade; count: number }[]
  by_team_role: { team_role: TeamRole; count: number }[]
  by_work_format: { work_format: WorkFormat; count: number }[]
  by_discipline: { discipline: Discipline; count: number }[]
  fsp_verified_total: number
}

type MatchQuery = {
  stacks?: Stack[]
  grades?: Grade[]
  team_roles?: TeamRole[]
  work_formats?: WorkFormat[]
  city?: string | null
  skills_required?: string[]         // id навыков
  skills_optional?: string[]
  strict_skills?: boolean            // по умолчанию false
  fsp_verified_only?: boolean        // по умолчанию false
  confirmed_only?: boolean           // по умолчанию false
  disciplines?: Discipline[]
  salary_max?: number | null
  text?: string | null               // до 2000 символов
  vacancy_id?: number | null         // своя вакансия: её поля дополняют запрос
  limit?: number                     // 1..50, по умолчанию 20
  offset?: number                    // 0..500
}

type CandidateBrief = {
  id: number
  display_name: string               // 'Алексей С.'; после принятого оффера этого работодателя — полное ФИО
  city: string | null
  category: Category
  salary_expectation: number | null
  relocation: boolean
  fsp_linked: boolean
  sport_rank: SportRank | null
  about: string | null               // через redact_contacts, пока этот работодатель не получил принятый оффер
}

type CandidateMatch = {
  candidate: CandidateBrief
  score: number | null               // 0..100, один знак; null — запрос без навыков и текста
  components: { skill: number | null; text: number | null; track_record: number; confidence: number }   // каждый 0..1
  matched_skills: SkillEvidence[]
  missing_skills: { skill: string; title: string }[]
  top_achievements: { title: string; level: CompetitionLevel; place: number | null; year: number | null; verification: Verification }[]
  reasons: string[]                  // 2–4 коротких фразы по-русски
  offer_status: OfferStatus | null   // оффер этого работодателя этому кандидату (последний)
}

type SearchResponse = {
  total: number; limit: number; offset: number
  items: CandidateMatch[]
  parsed_query: { skills: string[]; stack: Stack | null; grade: Grade | null } | null   // что извлечено из text
}

type CandidateCard = CandidateBrief & {
  facts: Fact[]                      // title и evidence — через redact_contacts до принятого оффера этого работодателя
  work_formats: WorkFormat[]
  contacts: { email: string; telegram: string | null; phone: string | null } | null   // только при принятом оффере этого работодателя
  offers: { id: number; vacancy_id: number; vacancy_title: string; status: OfferStatus; salary: number; created_at: string }[]   // только офферы этого работодателя
}

type Vacancy = {
  id: number; title: string; description: string
  stack: Stack; grade: Grade; team_role: TeamRole | null
  skills_required: string[]; skills_optional: string[]
  work_formats: WorkFormat[]; city: string | null
  salary_from: number | null; salary_to: number | null
  is_active: boolean; created_at: string
  offers_count: number
}
type VacancyInput = Omit<Vacancy, 'id' | 'created_at' | 'offers_count'>

type EmployerOffer = {
  id: number; status: OfferStatus; salary: number; message: string | null
  created_at: string; responded_at: string | null
  candidate_comment: string | null   // после redact_contacts, пока оффер не принят
  vacancy: { id: number; title: string }
  candidate: CandidateBrief
  contacts: { email: string; telegram: string | null; phone: string | null } | null   // только при accepted
}
```

- `GET /employer/profile` → `EmployerProfile`
- `GET /employer/categories?team_role=&work_format=` → `CategoryMatrix`.
  Все счётчики — только по кандидатам с `visible = true` и определённым стеком
  (тот же отбор, что в поиске); параметры сужают отбор.
- `POST /employer/search` — `MatchQuery` → `SearchResponse`
- `GET /employer/candidates/{id}` → `CandidateCard`
- `GET /employer/vacancies` → `Vacancy[]` (свои, новые сверху)
- `POST /employer/vacancies` — `VacancyInput` → 201 `Vacancy`
- `PATCH /employer/vacancies/{id}` — частичный `VacancyInput` → `Vacancy`
- `POST /employer/offers` — `{ candidate_id, vacancy_id, salary (> 0), message?: string (до 1000) }` → 201 `EmployerOffer`.
  Вакансия не найдена или чужая → `NOT_FOUND`; кандидат не найден или скрыт →
  `NOT_FOUND`; вакансия неактивна → `VACANCY_INACTIVE`; оффер по этой паре уже
  есть → `OFFER_ALREADY_SENT`.
- `GET /employer/offers` → `EmployerOffer[]` (свои, новые сверху)

## Мок реестра ФСП (без авторизации, только чтение)

Предлагаемый формат интеграции; в MVP отдаёт вымышленные данные. Включается
`FSP_MOCK_ROUTES_ENABLED`.

```ts
type FspAthletePublic = {
  fsp_id: string
  short_name: string                 // 'Смирнов А. И.'
  region: string | null
  ranks: { rank: SportRank; discipline: Discipline; assigned_at: string; order_no: string }[]
  results: {
    result_id: string
    competition: { competition_id: string; title: string; discipline: Discipline; level: CompetitionLevel; kind: 'championship' | 'cup' | 'junior_championship' | 'festival'; date_start: string; date_end: string; city: string; format: 'team' | 'individual'; participants_total: number }
    place: number
    team_name: string | null
    team_role: 'captain' | 'backend' | 'frontend' | 'ml' | 'analyst' | 'designer' | 'member' | null
    protocol_url: string
  }[]
}
```

- `GET /fsp-mock/athletes/{fsp_id}` → `FspAthletePublic`. Дата рождения и город
  спортсмена в ответах мока не бывают никогда.
