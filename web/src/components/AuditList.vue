<script setup lang="ts">
import InlineMessage from '@/components/ui/InlineMessage.vue'
import TimeText from '@/components/TimeText.vue'
import { auditActionWords, auditResultWords, auditTargetPath } from '@/lib/actions'
import type { AuditEntry } from '@/lib/types'

/**
 * The AuditList card: the audit log's entries between hairline rules, newest first. Each is the
 * action and its target (linked to the task's or group's page), what came of it, then who asked,
 * when, and Cloudflare's ray id. A plain result is ink; anything else is an InlineMessage in its
 * tone, so a refusal never reads as done. Every field is picked by name.
 */
defineProps<{ entries: AuditEntry[]; now: Date }>()
</script>

<template>
  <ul v-if="entries.length" id="audit-list" class="divide-y divide-line border-y border-line">
    <li
      v-for="(entry, i) in entries"
      :id="`audit-${i}`"
      :key="i"
      :data-result="entry.result ?? ''"
      class="grid gap-1 py-4"
    >
      <p class="body">
        <span class="font-semibold">{{ auditActionWords(entry) }}</span>
        {{ ' ' }}
        <RouterLink
          v-if="auditTargetPath(entry)"
          :to="auditTargetPath(entry)!"
          class="font-mono break-all underline underline-offset-[3px] hover:decoration-2"
          >{{ entry.target.id }}</RouterLink
        >
        <span v-else class="text-ink-secondary">(an id the console refused to write down)</span>
      </p>
      <InlineMessage
        v-if="auditResultWords(entry).tone"
        :tone="auditResultWords(entry).tone!"
        :data-tone="auditResultWords(entry).tone"
      >
        <span :id="`audit-${i}-result`">{{ auditResultWords(entry).text }}</span>
      </InlineMessage>
      <p v-else :id="`audit-${i}-result`" class="caption">{{ auditResultWords(entry).text }}</p>
      <p :id="`audit-${i}-who`" class="caption flex flex-wrap gap-x-4 text-ink-secondary">
        <span class="break-all">{{ entry.email ?? 'Signed-in user not recorded' }}</span>
        <TimeText v-if="entry.at" :at="entry.at" :now="now" relative />
        <span v-if="entry.cf_ray"
          >ray <code class="font-mono break-all">{{ entry.cf_ray }}</code></span
        >
      </p>
    </li>
  </ul>
  <p v-else id="audit-empty" class="body text-ink-secondary">Nothing recorded yet.</p>
</template>
