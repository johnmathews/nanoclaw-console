import { watchEffect } from 'vue'
import { APP_NAME } from '@/lib/app'

/** The tab's title: the page's name, then the product's. */
export function usePageTitle(page: () => string): void {
  watchEffect(() => {
    document.title = `${page()} · ${APP_NAME}`
  })
}
