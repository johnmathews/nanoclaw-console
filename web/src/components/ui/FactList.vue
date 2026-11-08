<script setup lang="ts">
/**
 * The FactList card: label and value pairs as a description list. Two columns from 640px, label
 * above value on a phone. Each row is a Fact.
 */
</script>

<template>
  <dl
    class="grid grid-cols-1 gap-y-3 sm:grid-cols-[minmax(9rem,max-content)_1fr] sm:gap-x-6 sm:gap-y-2"
  >
    <slot />
  </dl>
</template>
