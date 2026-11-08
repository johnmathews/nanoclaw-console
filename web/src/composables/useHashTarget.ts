import { nextTick, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'

/**
 * Scrolls to the element a link's hash names (`/permissions#approval-…`) once the page's first
 * answer has drawn it. The router cannot: the element does not exist until the API answers.
 * Later refreshes leave the scroll alone.
 */
export function useHashTarget(ready: Ref<boolean>): void {
  const route = useRoute()
  const stop = watch(
    ready,
    async (isReady) => {
      if (!isReady) return
      stop()
      if (!route.hash) return
      await nextTick()
      document.getElementById(decodeURIComponent(route.hash.slice(1)))?.scrollIntoView?.()
    },
    { immediate: true },
  )
}
