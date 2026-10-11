// Types of the HTTP contract (docs/API_CONTRACT.md, revision 2).
// Names and fields match the contract (and backend pydantic schemas) letter for letter.

// ---------- Errors ----------

export type ApiError = {
  success: false
  error_code: string
  message: string
  trace_id: string
  details: Record<string, unknown>
}

// ---------- Common ----------

export type Role = 'candidate' | 'employer'
export type Stack =
  | 'backend'
  | 'frontend'
  | 'fullstack'
  | 'mobile'
  | 'ml'
  | 'devops'
  | 'security'
  | 'embedded'
  | 'qa'
  | 'analyst'
export type Grade = 'intern' | 'junior' | 'middle' | 'senior'
export type TeamRole = 'lead' | 'developer' | 'researcher' | 'devops' | 'qa' | 'analyst'
export type WorkFormat = 'remote' | 'office' | 'hybrid'
export type Source = 'fsp' | 'test' | 'resume' | 'self'
export type Verification = 'verified' | 'tested' | 'parsed' | 'declared'
export type FactKind = 'skill' | 'experience' | 'achievement' | 'rank' | 'role'
export type Discipline = 'algorithmic' | 'product' | 'security' | 'robotics' | 'uav'
export type CompetitionLevel = 'municipal' | 'regional' | 'district' | 'national' | 'international'
export type SportRank = 'third' | 'second' | 'first' | 'kms' | 'ms'
export type AchievementResult = 'winner' | 'prize' | 'participant'
export type OfferStatus = 'sent' | 'accepted' | 'declined'

export type User = { id: number; email: string; role: Role; full_name: string }

export type Fact = {
  id: number
  kind: FactKind
  /** skill id | 'total' | 'fsp:<id>' | 'manual:<uuid>' | 'sport_rank' | 'fsp_captain' | 'fsp_team:<role>' | 'resume_lead' */
  key: string
  /** Ready-made Russian caption. */
  title: string
  value: Record<string, unknown>
  source: Source
  verification: Verification
  evidence: string | null
  created_at: string
}

// Shapes of Fact.value per kind (the contract keeps value open; see utils/facts.ts for safe readers).
export type SkillFactValue = { level: 1 | 2 | 3; score?: number }
export type ExperiencePosition = { title: string; company: string | null; period: string; years: number }
export type ExperienceFactValue = { years: number; positions: ExperiencePosition[] }
export type AchievementFactValue = {
  title: string
  discipline: Discipline | null
  level: CompetitionLevel
  place: number | null
  result: AchievementResult
  date: string | null
  year: number | null
  team_name: string | null
  team_role: string | null
  participants_total: number | null
  document_url: string | null
}
export type RankFactValue = {
  rank: SportRank
  discipline: Discipline | null
  assigned_at: string | null
  order_no: string | null
}
export type RoleFactValue = { reason: string }

export type Explanation = {
  label: string
  points: number
  source: Source | null
  verification: Verification | null
}

export type SkillEvidence = {
  skill: string
  title: string
  evidence: number
  best_source: Source
  verification: Verification
}

export type ConfidenceBreakdownItem = { label: string; points: number; max: number; done: boolean }

export type Category = {
  stack: Stack | null
  stack_confirmed: boolean
  grade: Grade | null
  grade_confirmed: boolean
  team_role: TeamRole | null
  team_role_source: Source | null
  work_formats: WorkFormat[]
  label: string
  grade_points: number
  grade_explanations: Explanation[]
  grade_note: string | null
  experience_years: number
  experience_points: number
  achievement_points: number
  stack_scores: { stack: Stack; score: number }[]
  top_skills: SkillEvidence[]
  confidence_index: number
  confidence_breakdown: ConfidenceBreakdownItem[]
}

// ---------- Service ----------

export type HealthResponse = { status: 'ok'; version: string; database: 'ok' | 'error' }

export type DictionaryItem<T extends string> = { id: T; title: string }

export type Dictionaries = {
  stacks: DictionaryItem<Stack>[]
  grades: DictionaryItem<Grade>[]
  team_roles: DictionaryItem<TeamRole>[]
  work_formats: DictionaryItem<WorkFormat>[]
  sources: DictionaryItem<Source>[]
  verifications: { id: Verification; title: string; weight: number }[]
  disciplines: DictionaryItem<Discipline>[]
  competition_levels: DictionaryItem<CompetitionLevel>[]
  sport_ranks: DictionaryItem<SportRank>[]
  skills: { id: string; title: string; stacks: string[] }[]
  cities: string[]
  fsp_registry_mode: 'mock' | 'live'
}

// ---------- Auth ----------

export type RegisterRequest = {
  email: string
  /** 8-72 bytes. */
  password: string
  role: Role
  full_name: string
  consent: true
  /** Candidate only; false by default (profile hidden). */
  show_profile?: boolean
  /** Required for employer. */
  company_name?: string
}

export type LoginRequest = { email: string; password: string }

export type AuthResponse = { access_token: string; token_type: 'bearer'; user: User }

// ---------- Candidate ----------

export type FspLink = { fsp_id: string; linked_at: string; region: string | null }
export type ResumeInfo = { filename: string | null; parsed_at: string; parser: 'rules'; chars: number }

export type CandidateProfile = {
  id: number
  user: User
  /** 'YYYY-MM-DD' */
  birth_date: string | null
  city: string | null
  work_formats: WorkFormat[]
  relocation: boolean
  salary_expectation: number | null
  about: string | null
  telegram: string | null
  phone: string | null
  visible: boolean
  fsp: FspLink | null
  resume: ResumeInfo | null
  category: Category
  facts: Fact[]
  updated_at: string
}

export type ProfilePatch = Partial<{
  full_name: string
  birth_date: string | null
  city: string | null
  work_formats: WorkFormat[]
  relocation: boolean
  salary_expectation: number | null
  about: string | null
  telegram: string | null
  phone: string | null
  visible: boolean
}>

export type FspLinkRequest = { fsp_id: string }

export type FspLinkResult = {
  athlete: { fsp_id: string; short_name: string; region: string | null }
  imported: { achievements: number; ranks: number; skills: number; roles: number }
  profile: CandidateProfile
}

export type ResumeInput = { file: File } | { text: string }

export type ResumePosition = {
  title: string
  company: string | null
  period: string
  years: number
  is_it: boolean
}

export type ResumeParseResult = {
  parser: 'rules'
  extracted: {
    skills: { skill: string; title: string; level: 1 | 2 }[]
    experience_years: number
    positions: ResumePosition[]
    work_formats: WorkFormat[]
    city: string | null
    salary_expectation: number | null
    is_lead: boolean
  }
  /** Which empty profile fields were filled from the resume. */
  applied_prefs: string[]
  profile: CandidateProfile
}

export type DemoResume = { text: string }

export type TestLevel = 1 | 2 | 3

export type TestInfo = {
  skill: string
  title: string
  description: string
  questions_per_session: number
  time_limit_seconds: number
  best_result: { level: TestLevel; level_title: string; score: number; submitted_at: string } | null
  /** Open, not yet expired session. */
  active_session_id: number | null
  /** Not null while the cooldown is in effect. */
  available_at: string | null
}

export type TestQuestion = { id: string; text: string; difficulty: 1 | 2 | 3; options: string[] }

export type TestSession = {
  session_id: number
  skill: string
  title: string
  started_at: string
  expires_at: string
  questions: TestQuestion[]
}

/** question id -> index of the chosen option, in the order options were delivered. */
export type TestSubmitRequest = { answers: Record<string, number> }

export type TestResult = {
  session_id: number
  skill: string
  /** 0..1, share of earned weight. */
  score: number
  level: 0 | 1 | 2 | 3
  passed: boolean
  correct: number
  total: number
  /** 'Не сдан' | 'Базовый' | 'Уверенный' | 'Продвинутый' */
  level_title: string
  profile: CandidateProfile
}

export type AchievementInput = {
  /** 3..200 */
  title: string
  /** 1990..current year */
  year: number
  level: CompetitionLevel
  result: AchievementResult
  discipline?: Discipline | null
  document_url?: string | null
}

export type VacancySummary = {
  id: number
  title: string
  description: string
  stack: Stack
  grade: Grade
  work_formats: WorkFormat[]
  city: string | null
  salary_from: number | null
  salary_to: number | null
}

export type CompanyInfo = { name: string; about: string | null; website: string | null; verified: boolean }

export type EmployerContacts = {
  contact_name: string | null
  contact_email: string | null
  contact_telegram: string | null
}

export type CandidateOffer = {
  id: number
  status: OfferStatus
  salary: number
  message: string | null
  created_at: string
  responded_at: string | null
  candidate_comment: string | null
  vacancy: VacancySummary
  company: CompanyInfo
  /** Only when accepted. */
  employer_contacts: EmployerContacts | null
}

export type OfferDecision = 'accept' | 'decline'

export type OfferRespondRequest = {
  decision: OfferDecision
  /** Up to 500 characters. */
  comment?: string
}

// ---------- Employer ----------

export type EmployerProfile = {
  id: number
  user: User
  company_name: string
  about: string | null
  website: string | null
  contact_name: string | null
  contact_email: string | null
  contact_telegram: string | null
  verified: boolean
}

export type CategoryMatrix = {
  total_candidates: number
  cells: { stack: Stack; grade: Grade; count: number; fsp_verified: number }[]
  by_stack: { stack: Stack; count: number }[]
  by_grade: { grade: Grade; count: number }[]
  by_team_role: { team_role: TeamRole; count: number }[]
  by_work_format: { work_format: WorkFormat; count: number }[]
  by_discipline: { discipline: Discipline; count: number }[]
  fsp_verified_total: number
}

export type CategoryMatrixParams = { team_role?: TeamRole | null; work_format?: WorkFormat | null }

export type MatchQuery = {
  stacks?: Stack[]
  grades?: Grade[]
  team_roles?: TeamRole[]
  work_formats?: WorkFormat[]
  city?: string | null
  skills_required?: string[]
  skills_optional?: string[]
  /** false by default */
  strict_skills?: boolean
  /** false by default */
  fsp_verified_only?: boolean
  /** false by default */
  confirmed_only?: boolean
  disciplines?: Discipline[]
  salary_max?: number | null
  /** Up to 2000 characters. */
  text?: string | null
  /** Own vacancy: its fields complement the query. */
  vacancy_id?: number | null
  /** 1..50, default 20 */
  limit?: number
  /** 0..500 */
  offset?: number
}

export type CandidateBrief = {
  id: number
  /** 'Алексей С.'; the full name after this employer's offer is accepted. */
  display_name: string
  city: string | null
  category: Category
  salary_expectation: number | null
  relocation: boolean
  fsp_linked: boolean
  sport_rank: SportRank | null
  about: string | null
}

export type MatchComponents = {
  skill: number | null
  text: number | null
  track_record: number
  confidence: number
}

export type TopAchievement = {
  title: string
  level: CompetitionLevel
  place: number | null
  year: number | null
  verification: Verification
}

export type CandidateMatch = {
  candidate: CandidateBrief
  /** 0..100, one decimal; null when the query has neither skills nor text. */
  score: number | null
  components: MatchComponents
  matched_skills: SkillEvidence[]
  missing_skills: { skill: string; title: string }[]
  top_achievements: TopAchievement[]
  reasons: string[]
  /** This employer's latest offer to the candidate. */
  offer_status: OfferStatus | null
}

export type ParsedQuery = { skills: string[]; stack: Stack | null; grade: Grade | null }

export type SearchResponse = {
  total: number
  limit: number
  offset: number
  items: CandidateMatch[]
  parsed_query: ParsedQuery | null
}

export type CandidateContacts = { email: string; telegram: string | null; phone: string | null }

export type CandidateCardOffer = {
  id: number
  vacancy_id: number
  vacancy_title: string
  status: OfferStatus
  salary: number
  created_at: string
}

export type CandidateCard = CandidateBrief & {
  facts: Fact[]
  work_formats: WorkFormat[]
  /** Only after this employer's offer is accepted. */
  contacts: CandidateContacts | null
  offers: CandidateCardOffer[]
}

export type Vacancy = {
  id: number
  title: string
  description: string
  stack: Stack
  grade: Grade
  team_role: TeamRole | null
  skills_required: string[]
  skills_optional: string[]
  work_formats: WorkFormat[]
  city: string | null
  salary_from: number | null
  salary_to: number | null
  is_active: boolean
  created_at: string
  offers_count: number
}

export type VacancyInput = Omit<Vacancy, 'id' | 'created_at' | 'offers_count'>

export type OfferCreateRequest = {
  candidate_id: number
  vacancy_id: number
  /** > 0 */
  salary: number
  /** Up to 1000 characters. */
  message?: string
}

export type EmployerOffer = {
  id: number
  status: OfferStatus
  salary: number
  message: string | null
  created_at: string
  responded_at: string | null
  candidate_comment: string | null
  vacancy: { id: number; title: string }
  candidate: CandidateBrief
  /** Only when accepted. */
  contacts: CandidateContacts | null
}

// ---------- FSP registry mock (no auth, read-only) ----------

export type FspTeamRole = 'captain' | 'backend' | 'frontend' | 'ml' | 'analyst' | 'designer' | 'member'

export type FspCompetition = {
  competition_id: string
  title: string
  discipline: Discipline
  level: CompetitionLevel
  kind: 'championship' | 'cup' | 'junior_championship' | 'festival'
  date_start: string
  date_end: string
  city: string
  format: 'team' | 'individual'
  participants_total: number
}

export type FspAthletePublic = {
  fsp_id: string
  /** 'Смирнов А. И.' */
  short_name: string
  region: string | null
  ranks: { rank: SportRank; discipline: Discipline; assigned_at: string; order_no: string }[]
  results: {
    result_id: string
    competition: FspCompetition
    place: number
    team_name: string | null
    team_role: FspTeamRole | null
    protocol_url: string
  }[]
}
