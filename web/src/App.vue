<script setup lang="ts">
import { onMounted } from 'vue'
import { APP_NAME } from '@/lib/app'
import { useOverviewStore } from '@/stores/overview'

const overview = useOverviewStore()
onMounted(() => void overview.load())
</script>

<template>
  <main class="mx-auto max-w-5xl px-4 py-8 sm:px-12 sm:py-12">
    <h1 class="display">{{ APP_NAME }}</h1>
    <p class="body-large mt-2 text-ink-secondary">
      NanoClaw’s health, groups, scheduled tasks and permissions, in one place.
    </p>

    <section class="mt-8 rounded-lg border border-line bg-panel p-6" aria-labelledby="status-title">
      <h2 id="status-title" class="title-2">Status</h2>
      <p
        v-if="overview.state === 'loading'"
        data-testid="api-status"
        class="mt-2 text-ink-secondary"
      >
        Asking the console’s API…
      </p>
      <p v-else-if="overview.state === 'ready'" data-testid="api-status" class="mt-2">
        The console’s API answered. The views arrive in the next releases.
      </p>
      <p v-else data-testid="api-status" role="alert" class="mt-2 text-error-ink">
        Couldn’t reach the console’s API. Reload the page to try again.
      </p>
    </section>
  </main>
</template>
