"""The plan of the demo data (SPEC section 10): who exists, what each person has, who offers what.

Pure data, no logic. `app/seed.py` turns it into rows with the same services the API uses, so
nothing here states a category: the stack, the grade and the role are always computed by the
domain from the facts.

Every person and organisation is invented. Names of the people who come from the FSP registry
are not listed here: they are read from `fsp_registry/data/registry.json`, so the identity
check of the link (name and birth date) always passes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateSpec:
    """One candidate; `fsp_id` takes the name and birth date from the registry record.

    `tests` are (skill, level) pairs of passed express tests; `manual` are keys of
    `MANUAL_ACHIEVEMENTS`. `gender` and `born` matter only for invented people (no `fsp_id`).
    """

    key: str
    fsp_id: str | None = None
    template: str | None = None
    tests: tuple[tuple[str, int], ...] = ()
    manual: tuple[str, ...] = ()
    gender: str = "m"
    born: tuple[int, int] = (1996, 2002)


@dataclass(frozen=True)
class EmployerSpec:
    key: str
    email: str
    company_name: str
    contact_name: str
    contact_email: str
    contact_telegram: str
    website: str
    about: str


@dataclass(frozen=True)
class VacancySpec:
    key: str
    employer: str
    title: str
    description: str
    stack: str
    grade: str
    team_role: str | None
    skills_required: tuple[str, ...]
    skills_optional: tuple[str, ...]
    work_formats: tuple[str, ...]
    city: str | None
    salary_from: int
    salary_to: int
    is_active: bool
    days_ago: int


@dataclass(frozen=True)
class OfferSpec:
    employer: str
    vacancy: str
    candidate: str
    salary: int
    status: str
    sent_days_ago: int
    message: str
    answered_days_ago: int | None = None
    candidate_comment: str | None = None


# --- the demo accounts (SPEC section 10) ---------------------------------------------------------

DEMO_CANDIDATE_EMAIL = "demo.candidate@fsp-career.test"
DEMO_CANDIDATE_NAME = "Смирнов Алексей Игоревич"
DEMO_CANDIDATE_BIRTH = (2003, 5, 14)
DEMO_CANDIDATE_CITY = "Казань"
DEMO_CANDIDATE_TELEGRAM = "@alexey_smirnov_demo"
DEMO_CANDIDATE_PHONE = "+7 900 000-00-17"
DEMO_CANDIDATE_ABOUT = (
    "Студент старших курсов, участвую в соревнованиях по спортивному программированию. "
    "Ищу первую работу, где можно писать серверный код и учиться у сильной команды."
)
DEMO_EMPLOYER_EMAIL = "demo.employer@fsp-career.test"

EMPLOYERS: tuple[EmployerSpec, ...] = (
    EmployerSpec(
        key="north",
        email=DEMO_EMPLOYER_EMAIL,
        company_name="Северный код",
        contact_name="Волкова Мария Андреевна",
        contact_email="hr@severny-kod.test",
        contact_telegram="@severny_kod_hr",
        website="https://severny-kod.example",
        about=(
            "Продуктовая студия: делаем веб-сервисы для логистики и торговли. Команды по пять-"
            "семь человек, релизы каждую неделю, код-ревью обязательно."
        ),
    ),
    EmployerSpec(
        key="orbita",
        email="hr@orbita-soft.test",
        company_name="Орбита Софт",
        contact_name="Мельников Илья Сергеевич",
        contact_email="jobs@orbita-soft.test",
        contact_telegram="@orbita_soft_jobs",
        website="https://orbita-soft.example",
        about=(
            "Программное обеспечение для связи со спутниками и наземных станций: серверная "
            "часть, обработка телеметрии, встраиваемые системы."
        ),
    ),
    EmployerSpec(
        key="neuro",
        email="hr@neurolab.test",
        company_name="Нейролаб",
        contact_name="Савельева Дарья Олеговна",
        contact_email="team@neurolab.test",
        contact_telegram="@neurolab_team",
        website="https://neurolab.example",
        about=(
            "Лаборатория прикладного машинного обучения: классификация обращений, поиск по "
            "документам, аналитика для клиентских сервисов."
        ),
    ),
)

# SPEC section 10: six vacancies; "Северный код" has an active "Python-разработчик" and no
# offer to the demo candidate on it.
VACANCIES: tuple[VacancySpec, ...] = (
    VacancySpec(
        key="north_python",
        employer="north",
        title="Python-разработчик",
        description=(
            "Развиваем сервис бронирования и расчёта доставки. Задачи: новые методы API на "
            "FastAPI, схемы в PostgreSQL и миграции, тесты и разбор инцидентов вместе с "
            "командой. Подойдёт сильный Junior или Middle; если у вас есть результаты "
            "соревнований по программированию, расскажите о них."
        ),
        stack="backend",
        grade="middle",
        team_role="developer",
        skills_required=("python", "fastapi", "postgresql"),
        skills_optional=("docker", "git", "redis"),
        work_formats=("remote", "hybrid"),
        city="Москва",
        salary_from=140_000,
        salary_to=230_000,
        is_active=True,
        days_ago=20,
    ),
    VacancySpec(
        key="north_vue",
        employer="north",
        title="Frontend-разработчик (Vue)",
        description=(
            "Личный кабинет клиента и панель диспетчера на Vue 3 и TypeScript. Работаем по "
            "макетам из Figma, держим общую библиотеку компонентов."
        ),
        stack="frontend",
        grade="middle",
        team_role="developer",
        skills_required=("vue", "typescript"),
        skills_optional=("html-css", "figma", "git"),
        work_formats=("remote",),
        city=None,
        salary_from=180_000,
        salary_to=260_000,
        is_active=True,
        days_ago=14,
    ),
    VacancySpec(
        key="orbita_junior",
        employer="orbita",
        title="Junior Python-разработчик",
        description=(
            "Сервисы приёма и разбора телеметрии со спутников. Начнёте с небольших задач под "
            "присмотром наставника, через три месяца возьмёте свой модуль."
        ),
        stack="backend",
        grade="junior",
        team_role="developer",
        skills_required=("python", "sql"),
        skills_optional=("git", "linux"),
        work_formats=("remote", "hybrid"),
        city="Москва",
        salary_from=100_000,
        salary_to=150_000,
        is_active=True,
        days_ago=9,
    ),
    VacancySpec(
        key="orbita_embedded",
        employer="orbita",
        title="Инженер встраиваемых систем",
        description=(
            "Прошивки для наземных станций и бортовых контроллеров на C++. Работа с "
            "микроконтроллерами, отладка протоколов обмена, стендовые испытания."
        ),
        stack="embedded",
        grade="middle",
        team_role="developer",
        skills_required=("cpp", "microcontrollers"),
        skills_optional=("ros", "linux"),
        work_formats=("office", "hybrid"),
        city="Москва",
        salary_from=220_000,
        salary_to=320_000,
        is_active=True,
        days_ago=25,
    ),
    VacancySpec(
        key="neuro_ml",
        employer="neuro",
        title="ML-инженер",
        description=(
            "Модели классификации обращений и поиск по документам: от подготовки данных до "
            "вывода в работу. Нужен опыт обучения моделей на PyTorch и аккуратная оценка "
            "качества."
        ),
        stack="ml",
        grade="middle",
        team_role="researcher",
        skills_required=("python", "pytorch", "machine-learning"),
        skills_optional=("nlp", "docker", "pandas"),
        work_formats=("remote",),
        city=None,
        salary_from=280_000,
        salary_to=380_000,
        is_active=True,
        days_ago=11,
    ),
    VacancySpec(
        key="neuro_analyst",
        employer="neuro",
        title="Аналитик данных",
        description=(
            "Отчёты и проверка гипотез для клиентских сервисов: SQL, pandas, дашборды. "
            "Набор закрыт, вакансия оставлена в истории."
        ),
        stack="analyst",
        grade="junior",
        team_role="analyst",
        skills_required=("sql", "data-analysis"),
        skills_optional=("pandas", "bi-tools"),
        work_formats=("remote", "hybrid"),
        city=None,
        salary_from=100_000,
        salary_to=150_000,
        is_active=False,
        days_ago=60,
    ),
)

# Exactly one incoming offer for the demo candidate, from "Орбита Софт", status `sent`
# (SPEC section 10). The other five are in other states.
OFFERS: tuple[OfferSpec, ...] = (
    OfferSpec(
        employer="orbita",
        vacancy="orbita_junior",
        candidate="demo",
        salary=135_000,
        status="sent",
        sent_days_ago=2,
        message=(
            "Алексей, здравствуйте! Мы разрабатываем сервисы для связи со спутниками и ищем "
            "начинающего Python-разработчика. Нам близок ваш интерес к спортивному "
            "программированию: давайте обсудим задачи и старт с наставником."
        ),
    ),
    OfferSpec(
        employer="north",
        vacancy="north_python",
        candidate="lebedev",
        salary=225_000,
        status="accepted",
        sent_days_ago=9,
        answered_days_ago=7,
        message=(
            "Никита, здравствуйте! Ваш опыт с FastAPI и результаты на соревнованиях нам "
            "подходят. Предлагаем присоединиться к команде сервиса доставки."
        ),
        candidate_comment="Спасибо за предложение! Готов обсудить задачи и условия.",
    ),
    OfferSpec(
        employer="north",
        vacancy="north_python",
        candidate="orlova",
        salary=210_000,
        status="declined",
        sent_days_ago=12,
        answered_days_ago=10,
        message=(
            "Ксения, здравствуйте! Ищем backend-разработчика в команду бронирования. Готовы "
            "обсудить формат работы и размер вознаграждения."
        ),
        candidate_comment="Спасибо за предложение! Сейчас рассматриваю другой вариант.",
    ),
    OfferSpec(
        employer="north",
        vacancy="north_vue",
        candidate="g_front",
        salary=230_000,
        status="sent",
        sent_days_ago=3,
        message=(
            "Здравствуйте! Нам нужен frontend-разработчик на Vue для личного кабинета. "
            "Работа полностью удалённая, макеты готовит отдельный дизайнер."
        ),
    ),
    OfferSpec(
        employer="neuro",
        vacancy="neuro_ml",
        candidate="zakharova",
        salary=310_000,
        status="sent",
        sent_days_ago=1,
        message=(
            "Анна, здравствуйте! Ваши результаты по алгоритмам и опыт в машинном обучении "
            "нам интересны. Предлагаем заняться классификацией обращений клиентов."
        ),
    ),
    OfferSpec(
        employer="orbita",
        vacancy="orbita_embedded",
        candidate="sorokina",
        salary=270_000,
        status="accepted",
        sent_days_ago=14,
        answered_days_ago=12,
        message=(
            "Софья, здравствуйте! Ищем инженера на прошивки наземных станций. Ваш опыт с "
            "беспилотными системами и C++ очень кстати."
        ),
        candidate_comment="Спасибо, предложение интересное. Давайте созвонимся.",
    ),
)

# --- candidates ---------------------------------------------------------------------------------
# 29 people besides the demo candidate, who has no FSP link, resume or tests (SPEC section 10).
# Totals with the demo candidate: 30 candidates, 20 linked to the FSP registry, 26 with a
# resume, 16 with passed tests, 6 with an achievement added by hand.

CANDIDATES: tuple[CandidateSpec, ...] = (
    # FSP record and resume (17).
    CandidateSpec("lebedev", "FSP-2024-00329", "backend_middle"),
    CandidateSpec("zhuravleva", "FSP-2022-00058", "security_junior", tests=(("python", 1),)),
    CandidateSpec("lazarev", "FSP-2023-00013", "security_middle", tests=(("python", 1),)),
    CandidateSpec("frolova", "FSP-2024-00381", "ml_middle", tests=(("algorithms", 3),)),
    CandidateSpec("sorokina", "FSP-2025-00142", "embedded_middle", tests=(("algorithms", 2),)),
    CandidateSpec("ryabova", "FSP-2023-00127", "mobile_junior", manual=("robotics_regional",)),
    CandidateSpec("isaev", "FSP-2025-00072", "backend_junior", tests=(("python", 2),)),
    CandidateSpec("krylov_o", "FSP-2023-00379", "fullstack_middle", tests=(("javascript", 2),)),
    CandidateSpec("kudryavtsev", "FSP-2022-00053", "devops_middle", tests=(("python", 1),)),
    CandidateSpec("belyaev", "FSP-2024-00348", "backend_go_senior", tests=(("algorithms", 3),)),
    CandidateSpec("komarov", "FSP-2023-00281", "analyst_junior"),
    CandidateSpec("zakharova", "FSP-2022-00304", "ml_junior"),
    CandidateSpec("orlova", "FSP-2025-00017", "backend_junior", tests=(("sql", 2),)),
    CandidateSpec("krylov_l", "FSP-2022-00016", "qa_middle"),
    CandidateSpec("guseva", "FSP-2024-00048", "frontend_junior", manual=("hackathon_part",)),
    CandidateSpec("kovalev", "FSP-2024-00112", "embedded_junior", manual=("ctf_prize",)),
    CandidateSpec("dmitrieva", "FSP-2025-00310", "student_intern", tests=(("python", 1),)),
    # FSP record, no resume (3).
    CandidateSpec("frolov_a", "FSP-2023-00115"),
    CandidateSpec("tikhonova", "FSP-2025-00260", manual=("olympiad_prize",)),
    CandidateSpec("frolov_d", "FSP-2023-00014", manual=("hackathon_winner",)),
    # Resume only, invented people (9).
    CandidateSpec(
        "g_lead",
        template="backend_senior_lead",
        tests=(("python", 3), ("algorithms", 2)),
        born=(1992, 1994),
    ),
    CandidateSpec(
        "g_front", template="frontend_middle", tests=(("javascript", 2),), born=(1997, 1999)
    ),
    CandidateSpec("g_mobile", template="mobile_middle", born=(1996, 1998)),
    CandidateSpec(
        "g_analyst", template="analyst_middle", tests=(("sql", 2),), gender="f", born=(1995, 1998)
    ),
    CandidateSpec(
        "g_qa", template="qa_junior", tests=(("python", 2),), gender="f", born=(1998, 2001)
    ),
    CandidateSpec("g_front_jr", template="frontend_junior", born=(2001, 2003)),
    CandidateSpec(
        "g_student",
        template="student_intern",
        manual=("olympiad_city",),
        gender="f",
        born=(2004, 2005),
    ),
    CandidateSpec("g_devops", template="devops_middle", tests=(("python", 1),), born=(1996, 1998)),
    CandidateSpec("g_ml", template="ml_middle", tests=(("python", 2),), born=(1997, 1999)),
)

# Achievements added by hand: (title, year, level, result, discipline, document_url).
MANUAL_ACHIEVEMENTS: dict[str, tuple[str, int, str, str, str | None, str | None]] = {
    "hackathon_winner": ("Хакатон «Весна Кода»", 2025, "regional", "winner", "product", None),
    "olympiad_prize": (
        "Командная олимпиада «Вычислитель»",
        2022,
        "national",
        "prize",
        "algorithmic",
        None,
    ),
    "ctf_prize": ("CTF «Серый Хост»", 2024, "district", "prize", "security", None),
    "olympiad_city": (
        "Городская олимпиада по информатике",
        2022,
        "municipal",
        "winner",
        "algorithmic",
        None,
    ),
    "robotics_regional": (
        "Региональный турнир юных робототехников",
        2021,
        "regional",
        "winner",
        "robotics",
        "https://diplomas.example/robotics/2021-0417",
    ),
    "hackathon_part": ("Хакатон «Умный Двор»", 2025, "district", "participant", "product", None),
}

# --- invented people and short texts --------------------------------------------------------------

MALE_FIRST_NAMES = (
    "Иван", "Дмитрий", "Сергей", "Андрей", "Михаил", "Егор", "Владимир", "Павел", "Роман",
    "Станислав", "Артур", "Тимофей",
)  # fmt: skip
FEMALE_FIRST_NAMES = (
    "Анастасия", "Елена", "Наталья", "Ольга", "Юлия", "Виктория", "Дарья", "Полина",
)  # fmt: skip
# (male, female) patronymics.
PATRONYMICS = (
    ("Александрович", "Александровна"),
    ("Дмитриевич", "Дмитриевна"),
    ("Сергеевич", "Сергеевна"),
    ("Андреевич", "Андреевна"),
    ("Михайлович", "Михайловна"),
    ("Игоревич", "Игоревна"),
    ("Олегович", "Олеговна"),
    ("Николаевич", "Николаевна"),
)
# (male, female) surnames; none of them is a surname from the FSP registry.
SURNAMES = (
    ("Белозёров", "Белозёрова"),
    ("Данилов", "Данилова"),
    ("Ершов", "Ершова"),
    ("Зубков", "Зубкова"),
    ("Игнатьев", "Игнатьева"),
    ("Назаров", "Назарова"),
    ("Островский", "Островская"),
    ("Пестов", "Пестова"),
    ("Румянцев", "Румянцева"),
    ("Селезнёв", "Селезнёва"),
    ("Тарасов", "Тарасова"),
    ("Уваров", "Уварова"),
    ("Хохлов", "Хохлова"),
    ("Чернов", "Чернова"),
    ("Шестаков", "Шестакова"),
    ("Яковлев", "Яковлева"),
)
CITIES = (
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород",
    "Самара", "Краснодар", "Ростов-на-Дону", "Уфа",
)  # fmt: skip

WORK_FORMAT_CHOICES = (
    ("remote",),
    ("hybrid",),
    ("remote", "hybrid"),
    ("office",),
    ("office", "hybrid"),
    ("remote", "office", "hybrid"),
)

# "About me" texts by stack; nobody writes contacts there.
ABOUTS: dict[str, tuple[str, ...]] = {
    "backend": (
        "Люблю разбираться, как устроены сервисы под нагрузкой. "
        "Ищу команду, где ценят тесты и код-ревью.",
        "Пишу серверный код и слежу за тем, чтобы им было приятно "
        "пользоваться другим разработчикам.",
    ),
    "frontend": (
        "Собираю интерфейсы, которые быстро открываются и понятны с первого раза. "
        "Люблю аккуратные компоненты.",
        "Для меня хороший интерфейс начинается с разговора с пользователем, а не с макета.",
    ),
    "fullstack": (
        "Веду продукт от схемы базы до кнопки на экране и люблю видеть результат целиком.",
    ),
    "mobile": (
        "Делаю мобильные приложения, которые не падают и экономно расходуют батарею.",
    ),
    "ml": (
        "Интересно доводить модели до работы в продукте, а не только до красивой метрики.",
        "Люблю аккуратную оценку качества и честные эксперименты.",
    ),
    "devops": (
        "Автоматизирую выкладку и слежу за тем, чтобы релиз был скучным событием.",
    ),
    "security": (
        "Ищу уязвимости раньше, чем их найдут другие, и объясняю разработчикам, как их закрыть.",
    ),
    "embedded": (
        "Нравится работа на стыке кода и железа: датчики, контроллеры, стенды.",
    ),
    "qa": (
        "Строю автоматические проверки, которым доверяют, и люблю находить дефекты до релиза.",
    ),
    "analyst": (
        "Превращаю сырые данные в выводы, на основе которых можно принимать решения.",
    ),
    "general": (
        "Участвую в соревнованиях по программированию и ищу команду, где можно расти.",
    ),
}  # fmt: skip

# Salary expectations (thousand roubles, a range) for people without a resume.
SALARY_BY_GRADE: dict[str, tuple[int, int]] = {
    "intern": (40, 60),
    "junior": (80, 140),
    "middle": (180, 280),
    "senior": (320, 450),
}
