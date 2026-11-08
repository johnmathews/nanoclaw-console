import { onScopeDispose, ref, shallowRef, watch, type Ref } from 'vue'
import { ApiError, getJson } from '@/lib/api'

/** Every page refreshes through the backend this often (W8); the backend caches, the broker too. */
export const REFRESH_MS = 30_000

/** Why the last load failed: the HTTP status, or `null` when the request never got an answer. */
export type LoadFailure = { status: number | null }

/**
 * A view of the API that loads at once, then every 30 seconds while its page is open, and again
 * at once when `path` changes. A failed refresh keeps the last answer and sets `error`; the next
 * good answer clears it. `checkedAt` is when the last attempt finished: the page's "now".
 */
export function useApi<T>(path: Ref<string>) {
  const data = shallowRef<T | null>(null)
  const error = ref<LoadFailure | null>(null)
  const checkedAt = ref(new Date())
  let generation = 0

  async function refresh(): Promise<void> {
    const mine = ++generation
    const target = path.value
    try {
      const answer = await getJson<T>(target)
      if (mine !== generation) return
      data.value = answer
      error.value = null
    } catch (err) {
      if (mine !== generation) return
      error.value = { status: err instanceof ApiError ? err.status : null }
    }
    checkedAt.value = new Date()
  }

  let timer: ReturnType<typeof setInterval> | undefined
  watch(
    path,
    () => {
      data.value = null
      error.value = null
      clearInterval(timer)
      timer = setInterval(() => void refresh(), REFRESH_MS)
      void refresh()
    },
    { immediate: true },
  )
  onScopeDispose(() => {
    generation++
    clearInterval(timer)
  })

  return { data, error, checkedAt, refresh }
}
