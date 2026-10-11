import { defineStore } from 'pinia'
import { ref } from 'vue'

import { getErrorMessage } from '@/api/client'

export type ToastKind = 'success' | 'error' | 'info'
export type Toast = { id: number; kind: ToastKind; message: string }

const DURATION_MS: Record<ToastKind, number> = { success: 4000, info: 5000, error: 7000 }
const MAX_VISIBLE = 4

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<Toast[]>([])
  const timers = new Map<number, number>()
  let nextId = 1

  function dismiss(id: number): void {
    const timer = timers.get(id)
    if (timer !== undefined) {
      window.clearTimeout(timer)
      timers.delete(id)
    }
    toasts.value = toasts.value.filter((toast) => toast.id !== id)
  }

  function push(kind: ToastKind, message: string): number {
    const id = nextId
    nextId += 1
    toasts.value = [...toasts.value, { id, kind, message }].slice(-MAX_VISIBLE)
    timers.set(
      id,
      window.setTimeout(() => dismiss(id), DURATION_MS[kind]),
    )
    return id
  }

  /** Green confirmation: "Профиль сохранён". */
  function success(message: string): number {
    return push('success', message)
  }

  /** Neutral notice. */
  function info(message: string): number {
    return push('info', message)
  }

  /** Red error with a plain message. */
  function error(message: string): number {
    return push('error', message)
  }

  /** Red error built from a thrown value: uses `message` of the ApiError when there is one. */
  function fromError(err: unknown, fallback?: string): number {
    return push('error', getErrorMessage(err, fallback))
  }

  return { toasts, push, success, info, error, fromError, dismiss }
})
