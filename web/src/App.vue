<script setup lang="ts">
import AppHeader from '@/components/AppHeader.vue'
</script>

<!--
  The shell every page shares: a skip link, the Header card (product name and the page
  navigation), then the page. Pages own their h1, their answer line and their PageStatus.
-->
<template>
  <a
    id="skip-link"
    href="#main"
    class="body sr-only z-10 rounded-md bg-panel px-4 py-2 focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
  >
    Skip to the page
  </a>
  <AppHeader />
  <main id="main" tabindex="-1" class="mx-auto max-w-7xl px-4 pt-8 pb-16 sm:px-8 sm:pt-12">
    <RouterView />
  </main>
</template>
