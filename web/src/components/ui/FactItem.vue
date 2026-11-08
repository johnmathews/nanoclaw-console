<script setup lang="ts">
/**
 * One FactList row: on a phone the label sits above its value; from 640px the pair joins the
 * list's two columns. `valueId` is the value's stable DOM id.
 */
defineProps<{ label: string; valueId?: string }>()
</script>

<template>
  <div class="grid gap-0.5 sm:contents">
    <dt class="caption text-ink-secondary">{{ label }}</dt>
    <dd :id="valueId" class="caption min-w-0 break-words"><slot /></dd>
  </div>
</template>
