import { defineStore } from 'pinia'
import { getJson } from '@/lib/api'

/** GET /api/overview. A placeholder in the scaffold; the overview view fills it in. */
export type Overview = { status: string }

export type LoadState = 'loading' | 'ready' | 'error'

export const useOverviewStore = defineStore('overview', {
  state: () => ({
    state: 'loading' as LoadState,
    overview: null as Overview | null,
  }),
  actions: {
    async load(): Promise<void> {
      try {
        this.overview = await getJson<Overview>('/api/overview')
        this.state = 'ready'
      } catch {
        this.overview = null
        this.state = 'error'
      }
    },
  },
})
