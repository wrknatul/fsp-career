// Thin fetch wrapper: base path, bearer token, ApiError parsing, 401 handling.

import type { ApiError } from './types'

export const TOKEN_STORAGE_KEY = 'fsp_career_token'
export const API_BASE = '/api/v1'

// ---------- Token storage (localStorage may be blocked: every access is guarded) ----------

// Fallback for browsers where localStorage throws: keeps the token for the current tab.
let memoryToken: string | null = null

export function getStoredToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function storeToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // Storage is blocked (private mode): the session lives until the page is closed.
  }
  memoryToken = token
}

export function clearStoredToken(): void {
  memoryToken = null
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // Nothing to clear if storage is blocked.
  }
}

function currentToken(): string | null {
  return getStoredToken() ?? memoryToken
}

// ---------- Error class ----------

export type ApiRequestErrorInit = {
  status: number
  error_code: string
  message: string
  details?: Record<string, unknown>
  trace_id?: string | null
}

/** Thrown for every failed request: HTTP errors, malformed responses and network failures (status 0). */
export class ApiRequestError extends Error {
  readonly status: number
  readonly error_code: string
  readonly details: Record<string, unknown>
  readonly trace_id: string | null

  constructor(init: ApiRequestErrorInit) {
    super(init.message)
    this.name = 'ApiRequestError'
    this.status = init.status
    this.error_code = init.error_code
    this.details = init.details ?? {}
    this.trace_id = init.trace_id ?? null
  }

  get isNetwork(): boolean {
    return this.status === 0
  }
}

export function isApiRequestError(value: unknown): value is ApiRequestError {
  return value instanceof ApiRequestError
}

const DEFAULT_ERROR_MESSAGE = 'Что-то пошло не так. Попробуйте ещё раз.'

/** User-facing message for any thrown value. */
export function getErrorMessage(err: unknown, fallback: string = DEFAULT_ERROR_MESSAGE): string {
  if (err instanceof ApiRequestError) {
    return err.message || fallback
  }
  return fallback
}

/** True when the error has the given contract error_code. */
export function hasErrorCode(err: unknown, code: string): boolean {
  return err instanceof ApiRequestError && err.error_code === code
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function fieldFromLoc(loc: unknown): string | null {
  if (!Array.isArray(loc)) {
    return null
  }
  for (let i = loc.length - 1; i >= 0; i -= 1) {
    const part: unknown = loc[i]
    if (typeof part === 'string' && part !== 'body' && part !== 'query' && part !== 'path') {
      return part
    }
  }
  return null
}

function messageFrom(entry: Record<string, unknown>): string | null {
  for (const key of ['message', 'msg', 'detail']) {
    const value = entry[key]
    if (typeof value === 'string' && value !== '') {
      return value
    }
  }
  return null
}

/**
 * Field -> message map for a VALIDATION_ERROR (and similar) response.
 * The contract keeps `details` open, so several shapes are accepted:
 *   { fields: { email: 'text' | ['text'] } }
 *   { errors | detail: [{ field | loc, message | msg }] }
 *   { email: 'text' }   (flat map of strings)
 * For other error codes the map is empty.
 */
export function fieldErrors(err: unknown): Record<string, string> {
  const result: Record<string, string> = {}
  if (!(err instanceof ApiRequestError) || err.error_code !== 'VALIDATION_ERROR') {
    return result
  }
  const details = err.details

  const addMap = (map: Record<string, unknown>): void => {
    for (const [field, value] of Object.entries(map)) {
      if (typeof value === 'string' && value !== '') {
        result[field] = value
      } else if (Array.isArray(value) && typeof value[0] === 'string') {
        result[field] = value[0]
      }
    }
  }

  const addList = (list: unknown): void => {
    if (!Array.isArray(list)) {
      return
    }
    for (const entry of list) {
      if (!isRecord(entry)) {
        continue
      }
      const field = typeof entry.field === 'string' ? entry.field : fieldFromLoc(entry.loc)
      const message = messageFrom(entry)
      // An error of the whole body (a model-level check) has `field: ''`: no input to hang it on, so it is
      // left out and the page falls back to the toast with the server message.
      if (field !== null && field !== '' && message !== null && result[field] === undefined) {
        result[field] = message
      }
    }
  }

  if (isRecord(details.fields)) {
    addMap(details.fields)
  }
  addList(details.errors)
  addList(details.detail)
  if (Object.keys(result).length === 0) {
    addMap(details)
  }
  return result
}

// ---------- Server clock (for countdowns that must follow the server, not the client) ----------

let serverOffsetMs = 0

function syncServerClock(response: Response): void {
  const header = response.headers.get('date')
  if (header === null) {
    return
  }
  const serverMs = Date.parse(header)
  if (Number.isFinite(serverMs)) {
    serverOffsetMs = serverMs - Date.now()
  }
}

/** Current time in ms according to the server clock (offset taken from the latest `Date` header). */
export function serverNow(): number {
  return Date.now() + serverOffsetMs
}

// ---------- 401 handling ----------

type UnauthorizedHandler = () => void
let unauthorizedHandler: UnauthorizedHandler | null = null

/** Registered once in main.ts: logs out and navigates to /login. Called on 401 of a protected request. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

// ---------- Request ----------

export type QueryValue = string | number | boolean | null | undefined | readonly (string | number)[]
export type QueryParams = Record<string, QueryValue>

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  query?: QueryParams
  /** JSON body. */
  json?: unknown
  /** multipart/form-data body (resume upload). */
  form?: FormData
  /** false for login/register: no token, and a 401 is just an error, not a logout. Default true. */
  auth?: boolean
  signal?: AbortSignal
}

function buildQuery(query: QueryParams | undefined): string {
  if (query === undefined) {
    return ''
  }
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') {
      continue
    }
    if (typeof value === 'object') {
      for (const item of value) {
        params.append(key, String(item))
      }
    } else {
      params.append(key, String(value))
    }
  }
  const text = params.toString()
  return text === '' ? '' : `?${text}`
}

function fallbackMessage(status: number): string {
  if (status === 401) return 'Сессия истекла. Войдите снова.'
  if (status === 403) return 'Для этого действия не хватает прав.'
  if (status === 404) return 'Ничего не нашли. Возможно, это уже удалено.'
  if (status === 413) return 'Файл слишком большой.'
  if (status === 429) return 'Слишком много попыток. Подождите немного и попробуйте снова.'
  if (status >= 500) return 'Сервер временно недоступен. Попробуйте чуть позже.'
  return DEFAULT_ERROR_MESSAGE
}

function fallbackCode(status: number): string {
  if (status === 401) return 'UNAUTHORIZED'
  if (status === 403) return 'FORBIDDEN'
  if (status === 404) return 'NOT_FOUND'
  if (status >= 500) return 'INTERNAL_ERROR'
  return 'HTTP_ERROR'
}

function toApiError(body: unknown): ApiError | null {
  if (!isRecord(body)) {
    return null
  }
  if (typeof body.error_code !== 'string' || typeof body.message !== 'string') {
    return null
  }
  return {
    success: false,
    error_code: body.error_code,
    message: body.message,
    trace_id: typeof body.trace_id === 'string' ? body.trace_id : '',
    details: isRecord(body.details) ? body.details : {},
  }
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (text === '') {
    return null
  }
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, json, form, auth = true, signal } = options

  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = auth ? currentToken() : null
  if (token !== null) {
    headers.Authorization = `Bearer ${token}`
  }

  let body: BodyInit | undefined
  if (form !== undefined) {
    body = form // the browser sets the multipart boundary itself
  } else if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}${buildQuery(query)}`, { method, headers, body, signal })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw cause
    }
    throw new ApiRequestError({
      status: 0,
      error_code: 'NETWORK_ERROR',
      message: 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.',
    })
  }

  syncServerClock(response)

  if (response.ok) {
    if (response.status === 204) {
      return undefined as T
    }
    const data = await readBody(response)
    if (data === null) {
      throw new ApiRequestError({
        status: response.status,
        error_code: 'INVALID_RESPONSE',
        message: 'Сервер ответил в непонятном формате. Попробуйте ещё раз.',
      })
    }
    return data as T
  }

  const parsed = toApiError(await readBody(response))
  const error = new ApiRequestError({
    status: response.status,
    error_code: parsed?.error_code ?? fallbackCode(response.status),
    message: parsed !== null && parsed.message !== '' ? parsed.message : fallbackMessage(response.status),
    details: parsed?.details,
    trace_id: parsed?.trace_id ?? response.headers.get('x-trace-id'),
  })

  if (response.status === 401 && auth && token !== null && unauthorizedHandler !== null) {
    unauthorizedHandler()
  }
  throw error
}

export const http = {
  get: <T>(path: string, query?: QueryParams, signal?: AbortSignal): Promise<T> =>
    apiRequest<T>(path, { method: 'GET', query, signal }),
  post: <T>(path: string, json?: unknown, auth = true): Promise<T> =>
    apiRequest<T>(path, { method: 'POST', json, auth }),
  patch: <T>(path: string, json: unknown): Promise<T> => apiRequest<T>(path, { method: 'PATCH', json }),
  delete: <T>(path: string): Promise<T> => apiRequest<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, form: FormData): Promise<T> => apiRequest<T>(path, { method: 'POST', form }),
}
