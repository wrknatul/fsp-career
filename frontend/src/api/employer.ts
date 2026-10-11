// Employer cabinet routes (role `employer`). One function per contract route.

import { http } from './client'
import type {
  CandidateCard,
  CategoryMatrix,
  CategoryMatrixParams,
  EmployerOffer,
  EmployerProfile,
  MatchQuery,
  OfferCreateRequest,
  SearchResponse,
  Vacancy,
  VacancyInput,
} from './types'

const segment = (value: string | number): string => encodeURIComponent(String(value))

/** GET /employer/profile */
export function getEmployerProfile(): Promise<EmployerProfile> {
  return http.get<EmployerProfile>('/employer/profile')
}

/** GET /employer/categories?team_role=&work_format= */
export function getCategoryMatrix(params: CategoryMatrixParams = {}): Promise<CategoryMatrix> {
  return http.get<CategoryMatrix>('/employer/categories', {
    team_role: params.team_role,
    work_format: params.work_format,
  })
}

/** POST /employer/search */
export function searchCandidates(query: MatchQuery): Promise<SearchResponse> {
  return http.post<SearchResponse>('/employer/search', query)
}

/** GET /employer/candidates/{id} */
export function getCandidate(candidateId: number): Promise<CandidateCard> {
  return http.get<CandidateCard>(`/employer/candidates/${segment(candidateId)}`)
}

/** GET /employer/vacancies (own, newest first) */
export function listVacancies(): Promise<Vacancy[]> {
  return http.get<Vacancy[]>('/employer/vacancies')
}

/** POST /employer/vacancies -> 201 */
export function createVacancy(input: VacancyInput): Promise<Vacancy> {
  return http.post<Vacancy>('/employer/vacancies', input)
}

/** PATCH /employer/vacancies/{id} (partial VacancyInput) */
export function updateVacancy(vacancyId: number, patch: Partial<VacancyInput>): Promise<Vacancy> {
  return http.patch<Vacancy>(`/employer/vacancies/${segment(vacancyId)}`, patch)
}

/** POST /employer/offers -> 201 */
export function createOffer(request: OfferCreateRequest): Promise<EmployerOffer> {
  return http.post<EmployerOffer>('/employer/offers', request)
}

/** GET /employer/offers (own, newest first) */
export function listEmployerOffers(): Promise<EmployerOffer[]> {
  return http.get<EmployerOffer[]>('/employer/offers')
}
