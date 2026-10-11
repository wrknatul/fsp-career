import { onBeforeUnmount, ref, shallowRef } from 'vue'

import { getErrorMessage } from '@/api/client'

export type LoaderStatus = 'idle' | 'loading' | 'ready' | 'error'

/**
 * Load-on-mount helper that maps onto StateBlock states.
 *
 *   const { data, status, errorMessage, load } = useLoader(() => getProfile())
 *   <StateBlock v-if="status === 'loading'" state="loading" />
 *   <StateBlock v-else-if="status === 'error'" state="error" :text="errorMessage" @retry="load" />
 *   <template v-else-if="data"> ... </template>
 *
 * `data` is a shallow ref: replace the whole value (setData) instead of mutating fields.
 * Stale responses (a newer load() started meanwhile) are ignored.
 */
export function useLoader<T>(fetcher: () => Promise<T>, options: { immediate?: boolean } = {}) {
  const { immediate = true } = options
  const data = shallowRef<T | null>(null)
  const status = ref<LoaderStatus>('idle')
  const errorMessage = ref('')
  let runId = 0
  let disposed = false

  async function load(): Promise<void> {
    runId += 1
    const current = runId
    status.value = 'loading'
    errorMessage.value = ''
    try {
      const result = await fetcher()
      if (disposed || current !== runId) {
        return
      }
      data.value = result
      status.value = 'ready'
    } catch (err) {
      if (disposed || current !== runId) {
        return
      }
      errorMessage.value = getErrorMessage(err)
      status.value = 'error'
    }
  }

  /** Replace the data without a request (e.g. with the `profile` returned by an action). */
  function setData(value: T): void {
    data.value = value
    status.value = 'ready'
    errorMessage.value = ''
  }

  onBeforeUnmount(() => {
    disposed = true
  })

  if (immediate) {
    void load()
  }

  return { data, status, errorMessage, load, setData }
}
