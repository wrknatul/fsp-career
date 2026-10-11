# ФСП.Карьера — спецификация MVP (редакция 2)

Хакатон «Лидеры цифровой трансформации» 2026, спецтрек Федерации спортивного
программирования. Команда «Граф магистралей». Срок сдачи MVP — 11.10.2026.

Этот файл — источник требований для всех исполнителей. Контракт API —
`API_CONTRACT.md`, доменные типы заморожены в `backend/app/domain/types.py`.
Если документы расходятся: типы → контракт → спецификация (первый прав);
расхождение записать в отчёт.

Редакция 2 учитывает три внешних разбора плана (продукт, архитектура,
алгоритмы). Сознательно вырезано: LLM-разбор, внешние эмбеддинги, загрузка
`.docx`, разбор текста вакансии, образование из резюме.

## 1. Задача (условие организатора, дословно)

> Разработайте цифровую платформу (веб-сервис) для подбора ИТ-специалистов с
> обратной механикой: соискатели автоматически распределяются по категориям на
> основе объективно подтверждаемого профиля, а работодатель сам находит нужную
> категорию и выходит на конкретного кандидата с предложением и уровнем
> заработной платы. Задача не сводится к парсингу сторонних сайтов и витрине
> чужих вакансий: требуется самостоятельная платформа, которая связывает
> напрямую только работодателя и соискателя.

Что сдаём: работающий прототип веб-сервиса с исходным кодом, документированным
API, инструкцией по развёртыванию и краткой технической документацией. Крайне
желательна ссылка на развёрнутое решение; иначе — демо-видео и инструкция по
локальному запуску.

Ресурсы организатора: только брендбук ФСП (цветовая гамма). **Доступа к API и
данным реестра ФСП нет, структура данных не выдаётся** — работаем на собственных
тестовых данных и сами решаем, какие сведения о достижениях получать и
показывать. Отраслевая специфика, которую надо формализовать: стек, грейд, роль
в команде, формат работы.

## 2. Принципы продукта

1. **Обратная механика.** Соискатель не откликается на вакансии. Он собирает
   профиль, платформа сама относит его к категории, работодатель находит
   категорию и отправляет оффер с зарплатой. Кнопки «откликнуться» нет.
2. **Каждый факт профиля имеет источник и уровень подтверждения.**
3. **Объяснимость.** У грейда и у каждого результата поиска есть раскрываемое
   «почему». Неподтверждённое помечено как неподтверждённое.
4. **Персональные данные не покидают платформу.** Внешних вызовов нет вообще:
   разбор резюме — правила, текстовое сходство — локальный вектор.
5. **Никакого парсинга чужих площадок.** Вакансии заводит только работодатель.
6. **Честность про демо.** Реестр ФСП смоделирован; это написано в интерфейсе.

## 3. Демо-сценарий (обязан проходить без ошибок после `--reset`)

1. Вход демо-соискателем. Категория «не определена», во входящих один оффер от
   компании «Орбита Софт».
2. Привязка ФСП ID `FSP-2024-00117` → подтянулись 6 результатов и разряд КМС;
   факты помечены «Подтверждено ФСП»; категория стала `Backend · Junior` с
   пояснением «без опыта работы грейд не выше Junior».
3. Кнопка «подставить пример резюме» → разбор: навыки, 1,5 года опыта, формат
   работы; факты «Из резюме»; грейд стал `Middle`.
4. Экспресс-тест по Python (6 вопросов) → навык «Подтверждено тестом», опыт из
   резюме засчитан с большим доверием, баллы выросли.
5. Олимпиада вручную → факт «Заявлено», вклад в грейд 35%.
6. Вход демо-работодателем («Северный код»). Матрица «стек × грейд».
7. Поиск: фильтры + текст запроса → выдача с оценкой 0–100 и объяснением;
   переключатель «только с результатами ФСП» оставляет не меньше 5 кандидатов.
8. Карточка демо-соискателя («Алексей С.», без контактов) → оффер с зарплатой
   по вакансии «Python-разработчик».
9. Вход соискателем → оффер во входящих → «Принять» → стороны видят контакты
   друг друга, работодатель видит полное ФИО.

## 4. Справочники

Идентификаторы — английские строки, подписи — русские.

**Стеки:** `backend` Backend, `frontend` Frontend, `fullstack` Fullstack,
`mobile` Мобильная разработка, `ml` ML / Data Science, `devops` DevOps / SRE,
`security` Информационная безопасность, `embedded` Embedded / робототехника,
`qa` Тестирование, `analyst` Аналитика.

**Грейды:** `intern` Стажёр, `junior` Junior, `middle` Middle, `senior` Senior.

**Роли в команде:** `lead` Тимлид, `developer` Разработчик, `researcher`
Исследователь / алгоритмист, `devops` Инженер инфраструктуры, `qa`
Тестировщик, `analyst` Аналитик.

**Форматы работы:** `remote` Удалённо, `office` Офис, `hybrid` Гибрид.

**Источники:** `fsp` Реестр ФСП, `test` Тест платформы, `resume` Резюме,
`self` Указано соискателем.

**Уровни подтверждения и веса:**

| id | Подпись | Вес | Источник |
| --- | --- | --- | --- |
| `verified` | Подтверждено ФСП | 1.00 | `fsp` |
| `tested` | Подтверждено тестом | 0.85 | `test` |
| `parsed` | Из резюме | 0.55 | `resume` |
| `declared` | Заявлено соискателем | 0.35 | `self` |

**Дисциплины:** `algorithmic` Алгоритмическое программирование, `product`
Продуктовое программирование (хакатон), `security` Программирование систем
информационной безопасности, `robotics` Программирование робототехники, `uav`
Программирование БАС.

**Уровень соревнования:** `municipal` Муниципальный, `regional` Региональный,
`district` Федеральный округ, `national` Всероссийский, `international`
Международный. Набор уровней — допущение команды.

**Разряды и звания:** `third` III разряд, `second` II разряд, `first` I
разряд, `kms` КМС, `ms` Мастер спорта России. МСМК, ЗМС и юношеские разряды в
MVP не учитываются. Баллы за разряды условные и уточняются с ФСП — так и
написать в документации.

**Вид соревнования (только реестр):** `championship` Чемпионат, `cup` Кубок,
`junior_championship` Первенство, `festival` Фестиваль.

### Онтология навыков

Файл `backend/app/domain/data/skills.json`: `{id, title, aliases[], stacks}`,
`stacks` — словарь `stack_id → "core" | "secondary"`. Таблица ниже обязательна
и исчерпывающа (66 навыков); алиасы подбирает исполнитель domain.

| Навык | core | secondary |
| --- | --- | --- |
| python | backend, ml | analyst, qa, devops |
| java | backend | mobile |
| kotlin | mobile | backend |
| swift | mobile | — |
| go | backend | devops |
| cpp | embedded | backend |
| csharp | backend | — |
| javascript | frontend | backend |
| typescript | frontend | backend |
| rust | — | backend, embedded |
| php | backend | — |
| sql | analyst | backend |
| html-css | frontend | — |
| fastapi, django, spring | backend | — |
| flask | — | backend |
| react, vue, angular | frontend | — |
| nodejs | backend | frontend |
| flutter, android, ios | mobile | — |
| react-native | mobile | frontend |
| pytorch, tensorflow, sklearn | ml | — |
| pandas | analyst | ml |
| docker | devops | backend |
| kubernetes, terraform, ansible | devops | — |
| linux | devops | security, embedded |
| ci-cd | devops | qa |
| nginx | — | devops |
| git | — | — |
| postgresql | backend | analyst |
| mongodb, redis, kafka, rabbitmq | — | backend |
| algorithms | backend | ml |
| product-development | — | backend, frontend |
| system-design | — | backend |
| infosec, pentest, cryptography, reverse-engineering | security | — |
| robotics, ros, uav, microcontrollers | embedded | — |
| machine-learning, nlp, llm | ml | — |
| computer-vision | ml | embedded |
| data-analysis, business-analysis, bi-tools | analyst | — |
| testing, test-automation, selenium | qa | — |
| jira | — | analyst, qa |
| figma, ui-ux | — | frontend |

Навыки дисциплин ФСП: `algorithmic` → `algorithms`, `product` →
`product-development`, `security` → `infosec`, `robotics` → `robotics`,
`uav` → `uav`.

Правила сопоставления алиасов (общие для резюме и текста запроса):

- шаблон `(?<![\w+#.])` + `re.escape(alias)` + `(?![\w+#])`, без учёта регистра;
- коротких алиасов `go`, `c`, `r`, кириллической «с» нет: Go — только `golang`
  и «язык go»; C++ — `c++`, `cpp`, «си++», «плюсы»;
- кириллические алиасы длиной от 5 символов сопоставляются по основе (алиас без
  последней гласной + `\w{0,3}`), чтобы ловить падежи: «питоном», «постгреса»;
- при пересечении вхождений побеждает длинный алиас (`react native` не даёт `react`);
- вхождение не засчитывается, если в четырёх словах перед ним стоит «не», «без»,
  «изучаю», «хочу», «планирую», «курс», «курсы».

## 5. Модель данных

SQLAlchemy 2.0, типы переносимые (тесты на SQLite, прод на PostgreSQL 17):
никаких `ARRAY`, `JSONB`, `pgvector`; структуры — `sa.JSON`; ключи — целые.
Даты — `DateTime(timezone=True)`, в коде только aware UTC; значение из SQLite
приходит naive — нормализовать помощником `as_utc()`. `created_at` задаёт
приложение. Фильтрация по JSON, сравнение строк с кириллицей и регистром —
только в Python, не в SQL.

- `users`: id, email (unique; `lower().strip()` при записи), password_hash,
  role, full_name, consent_at (обязательно), created_at.
- `candidates`: id, user_id (unique), birth_date, city, work_formats (JSON),
  relocation (bool), salary_expectation (int, nullable), about, telegram,
  phone, visible (bool; при регистрации `false`, пока соискатель явно не
  разрешил показ), fsp_id (nullable, unique), fsp_linked_at, fsp_region,
  resume_text, resume_filename, resume_parsed_at, category (JSON, тип
  `Category`), embedding (JSON list[float]), updated_at.
- `profile_facts`: id, candidate_id, kind (`skill` | `experience` |
  `achievement` | `rank` | `role`), key, title (готовая подпись — её задаёт
  домен), value (JSON), source, verification, evidence, created_at.
  Уникальность: (candidate_id, kind, key, source).
- `employers`: id, user_id (unique), company_name, about, website,
  contact_name, contact_email, contact_telegram, verified (bool, по умолчанию
  `false`; у демо-компаний `true`).
- `vacancies`: id, employer_id, title, description, stack, grade, team_role
  (nullable), skills_required (JSON), skills_optional (JSON), work_formats
  (JSON), city, salary_from, salary_to, is_active, created_at.
- `offers`: id, employer_id, candidate_id, vacancy_id, salary (int > 0),
  message, status (`sent` → `accepted` | `declined`, терминальные),
  candidate_comment, created_at, responded_at. Уникальность:
  (vacancy_id, candidate_id). Контакты в оффер не копируются — вычисляются на
  чтении по статусу. Срока действия в MVP нет (записать как ограничение).
- `test_sessions`: id, candidate_id, skill, started_at, expires_at,
  submitted_at, score, level, answers (JSON).
- `link_attempts`: id, user_id, created_at — для лимита привязки ФСП.

Пересчёт: после любого изменения фактов или настроек вызывается
`app.services.profile.recompute_candidate(db, candidate)` — обновляет
`category` и `embedding`. `category = NULL` означает «ещё не считали» и
трактуется как `categorizer.categorize([], prefs)`.

Гонки: ответ на оффер — `UPDATE offers SET status=… WHERE id=:id AND
status='sent'`, `rowcount == 0` → `OFFER_ALREADY_RESPONDED`. `IntegrityError`
при создании оффера → `OFFER_ALREADY_SENT`, при привязке ФСП →
`FSP_ALREADY_LINKED`. Ни одна ошибка целостности не должна дать 500.

## 6. Источники профиля

### 6.1. Реестр ФСП (смоделирован)

Адаптер `FspRegistryClient` с единственной реализацией `MockFspRegistry`,
читающей `backend/app/fsp_registry/data/registry.json`:

```
FspAthlete {
  fsp_id: "FSP-2024-00117", full_name, birth_date, region, city,
  ranks: [{rank, discipline, assigned_at, order_no}],
  results: [{
    result_id,
    competition: {competition_id, title, discipline, level, kind,
                  date_start, date_end, city, format: "team" | "individual", participants_total},
    place, team_name?, team_role?: "captain" | "backend" | "frontend" | "ml" | "analyst" | "designer" | "member",
    protocol_url
  }]
}
```

`birth_date` и `city` — внутренние поля сверки, наружу не отдаются никогда.
Публичный маршрут `GET /api/v1/fsp-mock/athletes/{fsp_id}` (включается
`FSP_MOCK_ROUTES_ENABLED`, по умолчанию `true`) сериализуется отдельной схемой
`FspAthletePublic`. Все записи реестра вымышлены: ФИО, даты, регионы, названия
соревнований и протоколы (`https://fsp.example/protocols/...`).

Привязка `POST /candidate/fsp/link`, порядок проверок:

1. В профиле нет ФИО или даты рождения → `PROFILE_INCOMPLETE`.
2. Больше 5 попыток за час у пользователя → 429 `RATE_LIMITED`.
3. ID не найден → `FSP_ATHLETE_NOT_FOUND`.
4. ID привязан к другому пользователю → `FSP_ALREADY_LINKED`; к этому же →
   `FSP_ALREADY_LINKED` с `details.linked_to_you = true`.
5. ФИО (без регистра, «ё» = «е», лишние пробелы) или дата рождения не совпали →
   `FSP_IDENTITY_MISMATCH`, без указания, какое поле.

Пока ФСП привязан, `PATCH /candidate/profile` с `full_name` или `birth_date`
→ 409 `FSP_LINKED_LOCKED`. Отвязка удаляет все факты `source = fsp`.

В интерфейсе: «Привязано по ФСП ID и совпадению ФИО и даты рождения. В демо
реестр смоделирован; в рабочей версии — вход через аккаунт ФСП».

Факты (`fsp_mapping.facts_from_fsp`), все `verified`:

- каждый результат → `achievement`, key `fsp:{result_id}`, evidence = `protocol_url`;
- старший разряд → `rank`, key `sport_rank`;
- по каждой дисциплине с результатами → `skill` навыка дисциплины; уровень 3 —
  призовое место (1–3) на `national`/`international`; 2 — призовое на
  `regional`/`district` или участие на `national`/`international`; иначе 1;
- был капитаном хотя бы раз → `role`, key `fsp_captain`, подпись «Капитан
  команды на соревнованиях ФСП» (в расчёте роли не участвует);
- командные роли `backend`/`frontend`/`ml`/`analyst` → `role`, key
  `fsp_team:{role}` (подсказка стека, см. 7.2).

### 6.2. Резюме

Вход: поле `text` (до 100 000 символов) либо файл `.txt` или `.pdf` до 2 МБ
(PDF — `pypdf`, не больше 20 страниц; зашифрованный или нечитаемый →
`UNSUPPORTED_FILE`). Разбор только правилами, `parser = "rules"`.

- Навыки — по правилам алиасов из раздела 4. Уровень 2, если ИТ-опыт от 1
  года, иначе 1. Уровня 3 из резюме не бывает.
- Опыт — диапазоны дат («2019 — 2022», «03.2020 – н.в.», «март 2021 — июнь
  2023»); «н.в.» = сегодня; конец периода не позже сегодня, будущие периоды
  отбрасываются; пересечения склеиваются. Не входят: диапазоны из разделов
  «Образование», «Обучение», «Курсы»; позиции без ИТ-признаков в названии
  (нет слов из словаря ролей и стеков); фразы «N лет в X» без дат.
- `is_lead` — только если «тимлид», «team lead», «руководитель
  группы/команды/разработки» стоит в строке должности позиции с датами.
- Формат работы (с тем же окном отрицаний), город (по основе, список 60
  крупных городов РФ), зарплатные ожидания (при любой неоднозначности — валюта,
  «до вычета», диапазон без «от» — `null`).
- Контакты из резюме в факты не попадают. `evidence` у фактов резюме —
  короткая цитата, прошедшая `redact_contacts`.

Факты: `skill` (parsed), `experience` key `total`, value
`{years, positions}`; при `is_lead` — `role` key `resume_lead`.

Повторная загрузка заменяет все факты `source = resume`. `DELETE
/candidate/resume` очищает `resume_text`, `resume_filename`,
`resume_parsed_at`, факты `source = resume` и пересчитывает профиль.
Пустые `city`, `work_formats`, `salary_expectation` профиля заполняются из
резюме; заполненные не перезаписываются.

### 6.3. Экспресс-тесты

Банк `backend/app/domain/data/questions.json`: 4 теста — `python`,
`javascript`, `sql`, `algorithms`; в каждом ровно 9 вопросов (по 3 на сложность
1, 2, 3), один верный из четырёх. Вопросы на русском, проверяют понимание, а
не память на синтаксис; двусмысленных и «с подвохом» нет.

Сессия — 6 вопросов (по 2 каждой сложности), сумма весов 12. Набор и порядок
вариантов детерминированы от `seed`; API считает
`seed = int(HMAC_SHA256(JWT_SECRET, str(session_id)).hexdigest()[:12], 16)`.
Лимит 8 минут, проверяется на сервере. Верные ответы клиенту не отдаются.

Уровень по сумме весов верных ответов: 12 → 3 «Продвинутый», ≥ 10 → 2
«Уверенный», ≥ 8 → 1 «Базовый», иначе 0 «Не сдан» (факт не создаётся).

Машина состояний:

- `start`: есть открытая неистёкшая сессия по навыку → вернуть её же (те же
  вопросы); иначе, если последняя сессия по навыку начата меньше
  `TEST_COOLDOWN_MINUTES` назад → `TEST_COOLDOWN` с `details.available_at`;
  иначе новая сессия, 201.
- `submit`: чужая или несуществующая сессия → 404 `TEST_NOT_FOUND`; уже сдана →
  `TEST_ALREADY_SUBMITTED`; `now > expires_at` → `TEST_SESSION_EXPIRED`, факт не
  создаётся; id вопроса не из сессии → 422; неотвеченные — неверные.
- Факт `skill` / source `test` — upsert: обновляется, только если новый уровень
  выше текущего; уровень 0 существующий факт не трогает.

Подпись в интерфейсе: «Экспресс-проверка из 6 вопросов: ориентир, а не
аттестация». В README: банк вопросов открыт вместе с кодом, в рабочей версии
хранится отдельно и ротируется.

### 6.4. Олимпиады и достижения вручную

Соискатель добавляет достижение вне реестра ФСП: олимпиады (ВсОШ, перечневые,
ICPC), хакатоны, CTF. Поля: `title`, `year`, `level`, `result` (`winner` |
`prize` | `participant`), `discipline?`, `document_url?`. Факт `achievement`,
key `manual:{uuid}`, source `self`, verification `declared`. Подпись: «Не
подтверждено. Вклад в грейд — 35%».

## 7. Алгоритмы (`backend/app/domain/`, чистые функции без БД и сети)

Все числа — в `scoring_config.py`.

### 7.1. Свидетельство по навыку

`w(f) = вес_подтверждения × levelFactor`; levelFactor: 1 → 0.6, 2 → 0.8, 3 → 1.0.
`E(s) = min(1.0, max_f w(f) + 0.1 × (число_разных_источников − 1))`.
Резюме даёт максимум 0.44, сданный тест — минимум 0.51: тест всегда сильнее.

### 7.2. Стек

`S(k) = min(3.0, Σ E(s) × (1.0 core | 0.5 secondary))`. Факт `fsp_team:{role}`
добавляет +0.5 одноимённому стеку, только если у него уже `S > 0`.

Основной стек: если `S(backend) ≥ 1.0`, `S(frontend) ≥ 1.0` и меньший не ниже
60% большего → `fullstack`; иначе argmax среди девяти стеков при `S ≥ 0.5`
(при равенстве — порядок справочника); иначе `null`. При `stack = null`
`grade` и `team_role` тоже `null`, подпись «Категория не определена».

`stack_confirmed` — у основного стека есть core-навык с фактом `verified` или
`tested` (для `fullstack` — у backend или frontend).

### 7.3. Грейд

`y` — ИТ-опыт в годах (максимум по фактам `experience`).

- **Опыт:** `raw = 12 × min(y, 2) + 9 × max(0, min(y, 8) − 2)`; доверие `k`:
  0.6 без сданных тестов, 0.8 с одним, 1.0 с двумя и более; баллы `k × raw`.
- **Тесты:** уровень 1 → 5, 2 → 10, 3 → 15 за тест, потолок 30.
- **Результаты ФСП:** `base[level] × place_factor`; base: municipal 2,
  regional 5, district 8, national 14, international 20; place_factor: 1 →
  1.0, 2–3 → 0.8, 4–10 → 0.5, иначе 0.25; потолок 40.
- **Разряд (старший):** third 3, second 5, first 8, kms 14, ms 20.
- **Вручную:** `base[level] × f × 0.35`; f: winner 1.0, prize 0.8,
  participant 0.25; потолок 10.

Пороги: < 6 → `intern`, 6–34.99 → `junior`, 35–69.99 → `middle`, ≥ 70 → `senior`.

Гейты (меняют грейд, не баллы) и `grade_note`:

- `y < 1` → не выше `junior`: «Спортивные результаты учтены, но без опыта
  работы грейд не выше Junior».
- `senior` только при `y ≥ 3` и хотя бы одном факте `verified` или `tested`,
  иначе `middle`: «Для Senior нужен опыт от 3 лет и подтверждение тестом или ФСП».
- Грейд `middle` и выше без единого факта `verified`/`tested`: «Грейд основан
  на опыте из резюме без подтверждения. Пройдите тест — опыт будет засчитан полнее».

`grade_confirmed` — есть хотя бы один факт `verified` или `tested`.
`grade_explanations` — вклады после потолков; инвариант:
`round(sum(points), 1) == grade_points`.

Опорные случаи для тестов: 10 лет резюме без тестов → 46.8, middle, не
подтверждён; 5 лет без тестов → 30.6, junior; 5 лет + тест уровня 2 → 50.8,
middle; 8 лет + два теста уровня 3 → 108, senior; студент с двумя
международными победами и без опыта → 40, junior (гейт); 1 год + тест уровня 3
→ 9.6 + 15 = 24.6, junior.

### 7.4. Роль в команде

`lead` — есть факт `role:resume_lead` и `y ≥ 3` (`team_role_source = resume`).
Иначе `researcher` — баллы ФСП по дисциплине `algorithmic` ≥ 20 при `y < 1`,
либо стек `ml`. Иначе по стеку: `devops` → `devops`, `qa` → `qa`, `analyst` →
`analyst`, остальные → `developer`.

### 7.5. Индекс подтверждённости (0–100)

`50 × [есть хотя бы один результат ФСП] + 25 × min(2, число сданных тестов)`.
Резюме и анкета в индекс не входят — это не подтверждение.

### 7.6. Текстовый вектор

Это лексическое сходство, а не семантика; в интерфейсе — «Совпадение с текстом
запроса». `profile_text`: навыки (с повтором по силе свидетельства), стек,
грейд, роль, названия достижений и дисциплин, «о себе», первые 4000 символов
резюме — всё после `redact_contacts`. `embed`: нижний регистр → токены →
стоп-слова ru+en выброшены → навыки онтологии нормализованы к id и получают
вес ×3; признаки — слова и символьные 3-граммы; знаковое хеширование в 384
измерения через `hashlib.md5`; tf логарифмический; L2-нормализация.

### 7.7. Матчинг

Жёсткие фильтры (кандидат должен иметь `visible = true` и стек):

- `stacks` — по `category.stack`; `fullstack` проходит фильтры `backend` и `frontend`;
- `grades`, `team_roles` — по `category`;
- `work_formats` — пересечение; кандидат без форматов проходит;
- `city` — совпал, либо `relocation = true`, либо и в запросе, и у кандидата
  есть `remote`;
- `fsp_verified_only` — есть факт `achievement` с `source = fsp`;
- `confirmed_only` — есть хотя бы один факт `verified` или `tested`;
- `disciplines` — есть результат ФСП в одной из дисциплин;
- `salary_max` — кандидат без ожиданий проходит;
- `strict_skills` — у каждого `skills_required` `E ≥ 0.4`.

Оценка 0–100: `0.45 × skill + 0.25 × text + 0.20 × track_record + 0.10 × confidence`:

- `skill = 0.8 × avg(E по required) + 0.2 × avg(E по optional)`; нет required —
  `avg` по optional; нет optional — `avg` по required;
- `text = max(0, cosine(embed(текст запроса), embedding кандидата))`;
- `track_record = 0.5 × min(1, (баллы ФСП + баллы разряда) / 40) + 0.5 × min(1, баллы опыта / 40)`;
- `confidence = индекс / 100`.

Нет навыков или нет текста — компонент `null`, веса остальных нормируются. Нет
ни навыков, ни текста — `score = null`, сортировка по `track_record` ↓,
`confidence` ↓, id ↑, интерфейс оценку не показывает. Иначе сортировка: оценка
↓, индекс ↓, id ↑.

Текст запроса: `matcher.parse_query_text` извлекает навыки (добавляются в
`skills_optional`), стек и грейд (только подсказка в `parsed_query`, не фильтр).
Вакансия → запрос: `stacks = [stack]`, `grades = [grade]`, `team_roles =
[team_role]` если задана, `work_formats`, `city`, навыки, `salary_max =
salary_to`, текст = название + описание. Неизвестный id навыка в запросе или
вакансии → 422 `VALIDATION_ERROR`.

### 7.8. Публичный интерфейс `app.domain` (типы — в `types.py`, не менять)

```
ontology.load_ontology() -> Ontology
ontology.normalize_skill(raw: str) -> str | None
ontology.skill_title(skill_id: str) -> str
ontology.find_skills(text: str) -> list[str]            # id в порядке первого вхождения
ontology.is_known_skill(skill_id: str) -> bool
ontology.dictionaries() -> dict                         # контрактный Dictionaries без fsp_registry_mode
redaction.redact_contacts(text: str | None) -> str | None   # e-mail, телефоны, @ники, t.me, ссылки → «[скрыто]»
redaction.display_name(full_name: str) -> str           # «Смирнов Алексей Игоревич» → «Алексей С.»
redaction.scrub_personal(text, *, full_name, birth_date, telegram, phone, email) -> str | None
                                                        # собственные ФИО, дата рождения, ник, телефон, почта человека → «[скрыто]»
resume_parser.extract_text(filename: str, content: bytes) -> str   # ResumeError(code) при ошибке
resume_parser.parse_resume(text: str, today: date | None = None, *, full_name: str | None = None) -> ParsedResume
quiz.list_tests() -> list[TestDef]
quiz.build_session(skill: str, seed: int) -> list[QuestionPublic]
quiz.grade_session(skill: str, seed: int, answers: dict[str, int]) -> QuizOutcome
fsp_mapping.facts_from_fsp(athlete: dict) -> list[FactData]
facts.manual_achievement_fact(uid, title, year, level, result, discipline, document_url) -> FactData
categorizer.categorize(facts: list[FactData], prefs: CandidatePrefs) -> Categorization
embedding.profile_text(facts, categorization, about: str | None, resume_text: str | None) -> str
embedding.embed(text: str) -> list[float]
embedding.cosine(a: list[float], b: list[float]) -> float
matcher.parse_query_text(text: str) -> ParsedQuery
matcher.score(query: MatchQuery, cand: CandidateSnapshot, query_vec: list[float] | None) -> MatchResult | None
matcher.rank(query: MatchQuery, candidates: list[CandidateSnapshot]) -> list[MatchResult]
```

Пакет не импортирует ничего из `app.api`, `app.models`, `app.db`, `app.core`.

## 8. Нефункциональные требования

- **Стек:** Python 3.12, FastAPI, SQLAlchemy 2.0 (синхронный), Alembic,
  PostgreSQL 17, psycopg 3; Vue 3 + Vite + Pinia + vue-router + TypeScript.
- **Конфигурация** — переменные окружения (`pydantic-settings`):
  `DATABASE_URL`, `JWT_SECRET`, `JWT_TTL_MINUTES` (720), `CORS_ORIGINS`,
  `SEED_DEMO_DATA` (true), `TEST_COOLDOWN_MINUTES` (1440; в compose 10),
  `MAX_UPLOAD_BYTES` (2097152), `FSP_REGISTRY_MODE` (`mock`),
  `FSP_MOCK_ROUTES_ENABLED` (true). В репозитории только `.env.example`.
- **Безопасность:** bcrypt (пароль 8–72 байта, проверять длину в байтах); JWT
  HS256; проверка роли на каждом защищённом маршруте; соискатель видит и
  меняет только своё, работодатель — только свои вакансии и офферы.
- **Приватность до принятого оффера** (и после отказа): работодатель видит
  `display_name` («Алексей С.») вместо ФИО; `about`, `evidence`, `title`
  фактов и `candidate_comment` проходят `redact_contacts` и `scrub_personal`
  (собственные ФИО, дата рождения, ник, телефон и почта соискателя, как бы он
  их ни записал); дата рождения,
  e-mail, телефон, telegram, текст резюме не отдаются работодателю никогда,
  кроме контактов после `accepted`. Скрытый и несуществующий кандидат
  неразличимы — оба 404 `NOT_FOUND`. `offset` поиска не больше 500.
- **Ошибки** — единый формат на все 4xx/5xx, включая валидацию и отсутствие
  токена (401, не 403): `{"success": false, "error_code": "…", "message":
  "по-русски", "trace_id": "uuid", "details": {}}`; `trace_id` дублируется в
  `X-Trace-Id`. Ответ 500 тоже в этом формате и с CORS-заголовками.
- **Тесты:** pytest; API-тесты на SQLite в памяти (`StaticPool`, `PRAGMA
  foreign_keys=ON`), схема через `Base.metadata.create_all`; отдельный тест
  прогоняет `alembic upgrade head` на временном SQLite-файле и сверяет набор
  таблиц и колонок с метаданными (`render_as_batch=True`). Перед сдачей —
  прогон на PostgreSQL 17 в Docker.
- **Язык:** интерфейс и сообщения — русский; код, комментарии, имена —
  английский. TypeScript: `type`, не `interface`; без `enum`.
- **Порты** (5432 и 8000 на машине заняты): API — 8100, веб — 8088, Vite —
  5173, PostgreSQL наружу — 5544.
- **Фронтенд ходит только на `/api/*`**: dev — прокси Vite на
  `http://localhost:8100`, сборка — nginx проксирует на сервис `backend`.

## 9. Интерфейс

Гамма ФСП (с fsp-russia.ru): основной `#402FFF`, тёмный `#1B1C21` / `#202129`,
светлый фон `#F4F4F6`, белый, серый текст `#9B9C9E`, границы `#EDEDED`,
предупреждение `#FF4D4F`, успех `#1FA971`. Шрифты: Inter — текст, JetBrains
Mono — заголовки и цифры (пакеты `@fontsource/*`, без внешних CDN). Свой CSS на
переменных, без UI-библиотек. Вёрстка от 375 px.

Бейдж источника у каждого факта: «Подтверждено ФСП» (основной цвет, заливка; в
режиме `mock` с меткой «демо»), «Подтверждено тестом» (зелёный), «Из резюме»
(серый), «Заявлено» (контур). В шапке при `fsp_registry_mode = mock` тонкая
плашка: «Демо-стенд: данные реестра ФСП смоделированы».

Страницы:

- `/` — что это и как работает для двух сторон; две кнопки входа в демо.
- `/login`, `/register` — переключатель роли; для соискателя два чекбокса:
  «согласен на обработку персональных данных» (обязателен) и «показывать мой
  профиль работодателям» (определяет `visible`), оба со ссылкой на `/privacy`.
- `/privacy` — какие данные собираются, зачем, кто их видит и когда, как отозвать.
- Соискатель: `/candidate` (категория, «почему этот грейд», индекс
  подтверждённости, чек-лист источников, переключатель видимости),
  `/candidate/profile` (анкета, резюме с кнопкой «подставить пример»,
  достижения вручную, все факты по группам), `/candidate/fsp`,
  `/candidate/tests` (список и прохождение с таймером), `/candidate/offers`.
- Работодатель: `/employer` (матрица «стек × грейд», срезы по роли, формату и
  дисциплине; клик ведёт в поиск с фильтром), `/employer/search`,
  `/employer/candidates/:id`, `/employer/vacancies`, `/employer/offers`.

У соискателя рядом с компанией в оффере — бейдж «Компания проверена» или «Не
проверена». Состояния загрузки, пустые состояния и ошибки (текст из `message`)
обязательны на каждой странице.

## 10. Демо-данные

`python -m app.seed` (`--reset` пересоздаёт всё); при пустой базе и
`SEED_DEMO_DATA=true` запускается на старте. Генерация детерминированная
(`random.Random(42)`), все люди и организации вымышлены.

- Реестр ФСП: 24 спортсмена, 14–18 соревнований всех пяти дисциплин и уровней.
- 30 соискателей (`visible = true`): 20 с привязкой ФСП, 26 с резюме, у 16
  сданы тесты, 6 с достижениями вручную; покрыты все стеки, кроме, возможно,
  одного-двух, и все грейды. Категории посчитаны функцией `categorize`,
  профили собраны теми же сервисами, что работают в API.
- Демо-соискатель `demo.candidate@fsp-career.test`: «Смирнов Алексей
  Игоревич», 2003-05-14, Казань, telegram `@alexey_smirnov_demo`, телефон
  `+7 900 000-00-17`, `visible = true`; **ФСП не привязан, резюме нет, тестов
  нет**. В реестре его запись `FSP-2024-00117`: КМС по алгоритмическому
  программированию; 6 результатов — 2 всероссийских призовых (алгоритмическое,
  3-е место; продуктовое, 2-е место, капитан), 2 окружных, 2 региональных;
  командная роль `backend`. Демо-резюме
  `backend/app/seed_data/demo_resume.txt`: 1,5 года ИТ-опыта (стажёр, затем
  младший backend-разработчик), Python, FastAPI, PostgreSQL, Docker, Git,
  удалённо или гибрид, Казань, ожидания «от 120 000».
- Работодатели: `demo.employer@fsp-career.test` — «Северный код»;
  `hr@orbita-soft.test` — «Орбита Софт»; `hr@neurolab.test` — «Нейролаб». Все
  `verified = true`. Всего 6 вакансий; у «Северного кода» есть активная
  «Python-разработчик» (backend, junior/middle) без офферов демо-соискателю.
- Офферы: 6 в разных статусах; демо-соискателю — ровно один входящий, от
  «Орбиты Софт», статус `sent`.
- Пароль всех демо-учёток: `demo12345`.

## 11. Структура, зоны и порядок работ

```
fsp-career/
  docs/SPEC.md, docs/API_CONTRACT.md, backend/app/domain/types.py   постановка — не менять
  backend/requirements*.txt, pytest.ini, pyproject.toml             заданы
  frontend/package.json, tsconfig*.json, vite.config.ts, index.html заданы
```

| Шаг | Исполнитель | Зона |
| --- | --- | --- |
| 1 | domain | `backend/app/domain/**` (кроме `types.py`), `backend/tests/domain/**` |
| 1 | core | `backend/app/main.py`, `core/{config,security,errors,timeutil}.py`, `db/**`, `models/**`, `schemas/**`, `api/deps.py`, `api/routes/{auth,health,fsp_mock,employer_profile}.py`, `fsp_registry/**`, `alembic/**`, `alembic.ini`, `tests/conftest.py`, `tests/api/test_{auth,health,fsp_mock,errors,migrations}.py`, заглушки маршрутов шага 2 |
| 1 | fe-shell | `frontend/src/**` кроме `pages/candidate/**` и `pages/employer/**` |
| 1 | infra-docs | `docker-compose.yml`, `.env.example`, `Makefile`, `README.md`, `backend/Dockerfile`, `backend/entrypoint.sh`, `frontend/Dockerfile`, `frontend/nginx.conf`, `docs/ARCHITECTURE.md`, `docs/FSP_INTEGRATION.md` |
| 2 | wire-candidate | `backend/app/services/profile.py`, `api/routes/candidate_{profile,fsp,resume,tests,achievements,offers}.py`, `tests/api/test_candidate_*.py` |
| 2 | wire-employer | `backend/app/services/search.py`, `api/routes/{vacancies,employer_search,employer_offers,reference}.py`, `tests/api/test_employer_*.py`, `tests/api/test_reference.py` |
| 2 | fe-candidate | `frontend/src/pages/candidate/**` |
| 2 | fe-employer | `frontend/src/pages/employer/**` |
| 3 | seed | `backend/app/seed.py`, `seed_data/**`, `tests/api/test_seed.py`, `tests/api/test_privacy.py`, `tests/api/test_demo_scenario.py` |
| 4 | integrate | любые файлы: Docker, PostgreSQL, сквозной сценарий, сверка фронтенда с API |

Правила стыков:

- `main.py` подключает все маршруты сразу; для файлов шага 2 исполнитель core
  создаёт заглушки с пустым `router`. Исполнители шага 2 `main.py` не трогают.
- Префиксы: `candidate_*` → `/candidate`; `employer_profile`, `vacancies`,
  `employer_search`, `employer_offers` → `/employer`; `reference` →
  `/reference`; `fsp_mock` → `/fsp-mock`; `auth` → `/auth`.
  `employer_search.py`: `GET /employer/categories`, `POST /employer/search`,
  `GET /employer/candidates/{id}`.
- pydantic-схемы контракта — `app/schemas/**`, имена классов равны именам типов
  контракта (`CandidateProfile`, `CandidateMatch`…); контрактный `Fact` —
  `schemas.Fact`, доменный — `domain.types.FactData`. `Category` в схемах — это
  `domain.types.Categorization` (переиспользовать, не дублировать).
- Стык шага 2 — только схема БД, `schemas/**` и `app.domain`. `wire-employer`
  не импортирует `services/profile.py`: снимок кандидата собирает сам из
  `candidates.category`, `candidates.embedding`, `profile_facts`.
- Регистрация соискателя создаёт строку `candidates` (`category = NULL`),
  работодателя — строку `employers`.
- `tests/conftest.py`: фикстуры `db`, `client`, `candidate_user`,
  `employer_user`, `candidate_headers`, `employer_headers`, `make_candidate`
  (фабрика соискателя с фактами и пересчитанной категорией — через домен).
- Страницы фронтенда шага 2 используют только общие компоненты, api-клиент и
  типы из зоны fe-shell; маршруты и заглушки страниц создаёт fe-shell.

Точка входа: `uvicorn app.main:app` из `backend/`; health —
`GET /api/v1/health`; OpenAPI — `/api/docs`, `/api/openapi.json`.

## 12. Критерии готовности MVP

1. `docker compose up --build` поднимает базу, API и веб; на
   `http://localhost:8088` демо-сценарий раздела 3 проходит целиком.
2. `backend/.venv/bin/pytest` зелёный; `npm run typecheck` и `npm run build`
   во `frontend/` без ошибок.
3. `/api/docs` показывает все маршруты контракта с описаниями.
4. Тест приватности: во всех ответах работодателю до `accepted` нет e-mail,
   telegram, телефона, даты рождения и полного ФИО ни одного соискателя — в том
   числе когда они вписаны в «о себе» и в текст резюме.
5. README: что это, запуск одной командой, развёртывание на сервере,
   демо-учётки, сценарий показа, ограничения MVP. Написаны
   `docs/ARCHITECTURE.md` и `docs/FSP_INTEGRATION.md`.
6. Делает команда, не исполнители: публичный стенд по ссылке и демо-видео на
   5 минут по разделу 3; на стенде только тестовые данные.
