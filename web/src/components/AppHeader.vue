<script setup lang="ts">
import { useRoute } from 'vue-router'
import { APP_NAME } from '@/lib/app'
import { NAV } from '@/lib/nav'

/**
 * The Header card: the product's name (a link to the overview) and the page navigation. The
 * current page's link carries aria-current="page" and a 2px underline; a page below it (a task
 * under Tasks) keeps its section underlined. On a phone the links wrap under the name.
 */
const route = useRoute()
</script>

<template>
  <header id="app-header" class="border-b border-line">
    <div
      class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-8 gap-y-1 px-4 py-2 sm:px-8"
    >
      <RouterLink
        id="app-name"
        to="/"
        class="inline-flex min-h-11 items-center font-serif text-[22px]/7 font-semibold"
      >
        {{ APP_NAME }}
      </RouterLink>
      <nav id="app-nav" aria-label="Pages">
        <ul class="-mx-2 flex flex-wrap">
          <li v-for="item in NAV" :key="item.name">
            <RouterLink
              :id="`nav-${item.name}`"
              :to="item.path"
              :data-active="route.meta.nav === item.name"
              :aria-current="route.name === item.name ? 'page' : undefined"
              class="body inline-flex min-h-11 items-center px-2 underline-offset-[6px] hover:underline data-[active=true]:underline data-[active=true]:decoration-2"
            >
              {{ item.label }}
            </RouterLink>
          </li>
        </ul>
      </nav>
    </div>
  </header>
</template>
