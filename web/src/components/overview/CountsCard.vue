<script setup lang="ts">
import FactItem from '@/components/ui/FactItem.vue'
import FactList from '@/components/ui/FactList.vue'
import AppPanel from '@/components/ui/AppPanel.vue'
import type { Counts } from '@/lib/types'

/** How much there is, in figures (a table of totals). A count whose read failed says so. */
defineProps<{ counts: Counts }>()

const ROWS: [key: keyof Counts, label: string, id: string][] = [
  ['groups', 'Groups', 'count-groups'],
  ['channels', 'Channels', 'count-channels'],
  ['wirings', 'Wirings', 'count-wirings'],
  ['sessions', 'Sessions', 'count-sessions'],
  ['tasks', 'Scheduled tasks', 'count-tasks'],
  ['tasks_paused', 'Paused tasks', 'count-tasks-paused'],
  ['tasks_overdue_on_resume', 'Would run at once if resumed', 'count-tasks-overdue'],
  ['pending_approvals', 'Pending approvals', 'count-pending-approvals'],
  ['dropped_messages', 'Dropped messages', 'count-dropped-messages'],
  ['host_errors_24h', 'Host errors, 24 hours', 'count-host-errors'],
  ['host_warnings_24h', 'Host warnings, 24 hours', 'count-host-warnings'],
]
</script>

<template>
  <AppPanel id="counts-card" title="Counts">
    <FactList>
      <FactItem v-for="[key, label, id] in ROWS" :key="key" :label="label" :value-id="id">
        {{ counts[key] ?? 'Couldn’t read' }}
      </FactItem>
    </FactList>
    <p class="caption">
      <RouterLink
        id="overview-tasks-link"
        to="/tasks"
        class="underline underline-offset-[3px] hover:decoration-2"
      >
        See every scheduled task
      </RouterLink>
    </p>
  </AppPanel>
</template>
