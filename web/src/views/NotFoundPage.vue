<script setup lang="ts">
import { usePageTitle } from '@/composables/usePageTitle'

usePageTitle(() => 'Page not found')
</script>

<template>
  <div class="grid gap-3">
    <h1 class="display">Page not found</h1>
    <p class="body">The console has no page at this address.</p>
    <p class="body">
      <RouterLink
        id="not-found-home"
        to="/"
        class="underline underline-offset-[3px] hover:decoration-2"
      >
        Go to the overview
      </RouterLink>
    </p>
  </div>
</template>
