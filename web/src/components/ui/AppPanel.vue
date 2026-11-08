<script setup lang="ts">
/**
 * The Panel card as a status card: a `section` on `panel` with a hairline border and the large
 * radius, titled by its `title-2` heading (aria-labelledby). It never clips its contents.
 */
defineProps<{ id: string; title: string }>()
</script>

<template>
  <section
    :id="id"
    :aria-labelledby="`${id}-title`"
    class="grid content-start gap-4 rounded-lg border border-line bg-panel p-4 shadow-overlay sm:p-6"
  >
    <h2 :id="`${id}-title`" class="title-2">{{ title }}</h2>
    <slot />
  </section>
</template>
