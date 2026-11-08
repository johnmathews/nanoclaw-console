<script setup lang="ts">
import InlineMessage from '@/components/ui/InlineMessage.vue'

/**
 * The AccessMark card: whether something can be written. Read-write is a caution, in words with
 * its icon, so it stands out in a list of mounts; read-only is plain `ink-secondary` text. Never
 * colour alone.
 */
defineProps<{
  readWrite: boolean
  /** The words for read-write; the card's default says what it means for a mount. */
  writeLabel?: string
  readLabel?: string
}>()
</script>

<template>
  <InlineMessage v-if="readWrite" tone="caution" data-access="read-write">{{
    writeLabel ?? 'Read-write'
  }}</InlineMessage>
  <span v-else class="caption text-ink-secondary" data-access="read-only">{{
    readLabel ?? 'Read-only'
  }}</span>
</template>
