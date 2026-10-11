"""Every tunable number of the domain algorithms (SPEC section 7).

Nothing in this module has behaviour: it is a flat list of constants so the
weights can be reviewed (and agreed with the FSP) in one place.
"""

from __future__ import annotations

# --- 7.1 Skill evidence -----------------------------------------------------------------------
VERIFICATION_WEIGHT: dict[str, float] = {
    "verified": 1.00,
    "tested": 0.85,
    "parsed": 0.55,
    "declared": 0.35,
}
# Order from the strongest to the weakest confirmation (used for tie-breaks).
VERIFICATION_ORDER: tuple[str, ...] = ("verified", "tested", "parsed", "declared")
LEVEL_FACTOR: dict[int, float] = {1: 0.6, 2: 0.8, 3: 1.0}
EXTRA_SOURCE_BONUS = 0.1
EVIDENCE_CAP = 1.0
TOP_SKILLS_LIMIT = 8

# --- 7.2 Stack --------------------------------------------------------------------------------
STACK_SCORE_CAP = 3.0
CORE_WEIGHT = 1.0
SECONDARY_WEIGHT = 0.5
FSP_TEAM_BONUS = 0.5
STACK_MIN_SCORE = 0.5
FULLSTACK_MIN_SCORE = 1.0
FULLSTACK_RATIO = 0.6
SCORE_EPSILON = 1e-9

# --- 7.3 Grade --------------------------------------------------------------------------------
EXPERIENCE_FAST_YEARS = 2.0
EXPERIENCE_FAST_RATE = 12.0
EXPERIENCE_SLOW_RATE = 9.0
EXPERIENCE_MAX_YEARS = 8.0
# Trust in the experience from a resume by the number of passed tests: 0, 1, 2 or more.
EXPERIENCE_TRUST_BY_TESTS: tuple[float, float, float] = (0.6, 0.8, 1.0)

TEST_POINTS: dict[int, float] = {1: 5.0, 2: 10.0, 3: 15.0}
TEST_POINTS_CAP = 30.0

FSP_LEVEL_BASE: dict[str, float] = {
    "municipal": 2.0,
    "regional": 5.0,
    "district": 8.0,
    "national": 14.0,
    "international": 20.0,
}
FSP_PLACE_FACTOR_WINNER = 1.0
FSP_PLACE_FACTOR_PRIZE = 0.8  # places 2..PRIZE_MAX_PLACE
FSP_PLACE_FACTOR_TOP = 0.5  # places PRIZE_MAX_PLACE+1..TOP_MAX_PLACE
FSP_PLACE_FACTOR_OTHER = 0.25
PRIZE_MAX_PLACE = 3
TOP_MAX_PLACE = 10
FSP_POINTS_CAP = 40.0

RANK_POINTS: dict[str, float] = {
    "third": 3.0,
    "second": 5.0,
    "first": 8.0,
    "kms": 14.0,
    "ms": 20.0,
}
# Weaker to stronger; used to pick the senior rank.
RANK_ORDER: tuple[str, ...] = ("third", "second", "first", "kms", "ms")

MANUAL_RESULT_FACTOR: dict[str, float] = {"winner": 1.0, "prize": 0.8, "participant": 0.25}
MANUAL_DISCOUNT = 0.35
MANUAL_POINTS_CAP = 10.0

GRADE_JUNIOR_FROM = 6.0
GRADE_MIDDLE_FROM = 35.0
GRADE_SENIOR_FROM = 70.0

# Gates: they change the grade but never the points.
GATE_NO_EXPERIENCE_YEARS = 1.0  # below this the grade is not higher than junior
GATE_SENIOR_MIN_YEARS = 3.0

# --- 7.4 Team role ----------------------------------------------------------------------------
LEAD_MIN_YEARS = 3.0
RESEARCHER_ALGORITHMIC_POINTS = 20.0
RESEARCHER_MAX_YEARS = 1.0  # strictly below this

# --- 7.5 Confidence index ---------------------------------------------------------------------
CONFIDENCE_FSP_POINTS = 50
CONFIDENCE_TEST_POINTS = 25
CONFIDENCE_MAX_TESTS = 2

# --- 7.6 Text vector --------------------------------------------------------------------------
EMBEDDING_DIM = 384
SKILL_FEATURE_WEIGHT = 3.0
NGRAM_SIZE = 3
PROFILE_RESUME_CHARS = 4000
# A skill with evidence 1.0 is repeated this many times in the profile text.
PROFILE_SKILL_REPEAT_MAX = 4
EMBEDDING_DECIMALS = 6

# --- 7.7 Matching -----------------------------------------------------------------------------
MATCH_WEIGHT_SKILL = 0.45
MATCH_WEIGHT_TEXT = 0.25
MATCH_WEIGHT_TRACK = 0.20
MATCH_WEIGHT_CONFIDENCE = 0.10
STRICT_SKILL_MIN_EVIDENCE = 0.4
SKILL_REQUIRED_SHARE = 0.8
SKILL_OPTIONAL_SHARE = 0.2
TRACK_POINTS_SCALE = 40.0
TRACK_SHARE = 0.5
TOP_ACHIEVEMENTS_LIMIT = 3
REASONS_MIN = 2
REASONS_MAX = 4
REASON_MISSING_SHOWN = 3  # missing skills named in the "Не хватает: ..." phrase
REASON_TEXT_MIN = 0.15  # text similarity below this is not worth a phrase
SCORE_DECIMALS = 1
COMPONENT_DECIMALS = 4

# --- Alias matching (SPEC section 4) ----------------------------------------------------------
NEGATION_WORDS: frozenset[str] = frozenset(
    {"не", "без", "изучаю", "хочу", "планирую", "курс", "курсы"}
)
NEGATION_WINDOW = 4
STEM_MIN_LENGTH = 5
STEM_SUFFIX_MAX = 3

# --- Resume parsing (SPEC section 6.2) --------------------------------------------------------
DAYS_PER_YEAR = 365.25
RESUME_SKILL_LEVEL2_MIN_YEARS = 1.0
MAX_PDF_PAGES = 20
SALARY_MIN = 10_000
SALARY_MAX = 5_000_000
EVIDENCE_MAX_CHARS = 140
EXPERIENCE_DECIMALS = 2
# Bounds that keep a hostile or broken file (one endless line, thousands of dates) cheap.
RESUME_CONTEXT_CHARS = 160  # text around a date range that can hold the job title
RESUME_MAX_RANGES = 300  # date ranges examined
RESUME_MAX_POSITIONS = 60  # positions kept

# --- Express tests (SPEC section 6.3) ----------------------------------------------------------
QUIZ_QUESTIONS_PER_LEVEL = 2
QUIZ_DIFFICULTIES: tuple[int, ...] = (1, 2, 3)
QUIZ_TIME_LIMIT_SECONDS = 480
# (minimum weight, level), checked from the top.
QUIZ_LEVEL_THRESHOLDS: tuple[tuple[int, int], ...] = ((12, 3), (10, 2), (8, 1))
QUIZ_LEVEL_TITLES: dict[int, str] = {0: "Не сдан", 1: "Базовый", 2: "Уверенный", 3: "Продвинутый"}
QUIZ_SCORE_DECIMALS = 4
