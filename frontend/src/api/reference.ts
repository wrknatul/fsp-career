// Service routes: health, dictionaries and the FSP registry mock (all without authorization).

import { http } from './client'
import type { Dictionaries, FspAthletePublic, HealthResponse } from './types'

/** GET /health */
export function getHealth(): Promise<HealthResponse> {
  return http.get<HealthResponse>('/health')
}

/** GET /reference/dictionaries */
export function getDictionaries(): Promise<Dictionaries> {
  return http.get<Dictionaries>('/reference/dictionaries')
}

/** GET /fsp-mock/athletes/{fsp_id} (demo registry, read-only) */
export function getFspAthlete(fspId: string): Promise<FspAthletePublic> {
  return http.get<FspAthletePublic>(`/fsp-mock/athletes/${encodeURIComponent(fspId)}`)
}
