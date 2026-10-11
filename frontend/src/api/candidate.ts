// Candidate cabinet routes (role `candidate`). One function per contract route.

import { http } from './client'
import type {
  AchievementInput,
  CandidateOffer,
  CandidateProfile,
  DemoResume,
  FspLinkResult,
  OfferRespondRequest,
  ProfilePatch,
  ResumeInput,
  ResumeParseResult,
  TestInfo,
  TestResult,
  TestSession,
  TestSubmitRequest,
} from './types'

const segment = (value: string | number): string => encodeURIComponent(String(value))

// ---------- Profile ----------

/** GET /candidate/profile */
export function getProfile(): Promise<CandidateProfile> {
  return http.get<CandidateProfile>('/candidate/profile')
}

/** PATCH /candidate/profile. full_name/birth_date with a linked FSP -> FSP_LINKED_LOCKED. */
export function patchProfile(patch: ProfilePatch): Promise<CandidateProfile> {
  return http.patch<CandidateProfile>('/candidate/profile', patch)
}

// ---------- FSP ----------

/** POST /candidate/fsp/link */
export function linkFsp(fspId: string): Promise<FspLinkResult> {
  return http.post<FspLinkResult>('/candidate/fsp/link', { fsp_id: fspId })
}

/** DELETE /candidate/fsp/link */
export function unlinkFsp(): Promise<CandidateProfile> {
  return http.delete<CandidateProfile>('/candidate/fsp/link')
}

// ---------- Resume ----------

/** POST /candidate/resume (multipart: field `file` or field `text`) */
export function uploadResume(input: ResumeInput): Promise<ResumeParseResult> {
  const form = new FormData()
  if ('file' in input) {
    form.append('file', input.file, input.file.name)
  } else {
    form.append('text', input.text)
  }
  return http.upload<ResumeParseResult>('/candidate/resume', form)
}

/** DELETE /candidate/resume */
export function deleteResume(): Promise<CandidateProfile> {
  return http.delete<CandidateProfile>('/candidate/resume')
}

/** GET /candidate/resume/demo */
export function getDemoResume(): Promise<DemoResume> {
  return http.get<DemoResume>('/candidate/resume/demo')
}

// ---------- Tests ----------

/** GET /candidate/tests */
export function listTests(): Promise<TestInfo[]> {
  return http.get<TestInfo[]>('/candidate/tests')
}

/** POST /candidate/tests/{skill}/start -> 201 (or 200 with the already open session) */
export function startTest(skill: string): Promise<TestSession> {
  return http.post<TestSession>(`/candidate/tests/${segment(skill)}/start`)
}

/** POST /candidate/tests/sessions/{session_id}/submit */
export function submitTest(sessionId: number, request: TestSubmitRequest): Promise<TestResult> {
  return http.post<TestResult>(`/candidate/tests/sessions/${segment(sessionId)}/submit`, request)
}

// ---------- Manual achievements ----------

/** POST /candidate/achievements -> 201 */
export function addAchievement(input: AchievementInput): Promise<CandidateProfile> {
  return http.post<CandidateProfile>('/candidate/achievements', input)
}

/** DELETE /candidate/achievements/{fact_id} (only own facts with source `self`) */
export function deleteAchievement(factId: number): Promise<CandidateProfile> {
  return http.delete<CandidateProfile>(`/candidate/achievements/${segment(factId)}`)
}

// ---------- Offers ----------

/** GET /candidate/offers (newest first) */
export function listOffers(): Promise<CandidateOffer[]> {
  return http.get<CandidateOffer[]>('/candidate/offers')
}

/** POST /candidate/offers/{id}/respond */
export function respondToOffer(offerId: number, request: OfferRespondRequest): Promise<CandidateOffer> {
  return http.post<CandidateOffer>(`/candidate/offers/${segment(offerId)}/respond`, request)
}
