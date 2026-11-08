<script setup lang="ts">
import { computed } from 'vue'
import FactItem from '@/components/ui/FactItem.vue'
import FactList from '@/components/ui/FactList.vue'
import AppPanel from '@/components/ui/AppPanel.vue'
import StatusMark from '@/components/ui/StatusMark.vue'
import TimeText from '@/components/TimeText.vue'
import { durationWords } from '@/lib/time'
import type { NanoclawHealth } from '@/lib/types'

/** NanoClaw's own /health, read by the broker: channels, message loop, queue, sessions, uptime. */
const props = defineProps<{ nanoclaw: NanoclawHealth; now: Date }>()

const healthy = computed(() => {
  const n = props.nanoclaw
  if (!n.available)
    return n.reason === 'not_answering'
      ? { status: 'failing' as const, label: 'Not answering' }
      : { status: 'unknown' as const, label: 'Unknown' }
  if (n.healthy === null) return { status: 'unknown' as const, label: 'Unknown' }
  return n.healthy
    ? { status: 'ok' as const, label: 'Healthy' }
    : { status: 'failing' as const, label: 'Unhealthy' }
})

const known = (n: number | null) => (n === null ? 'not known' : String(n))
</script>

<template>
  <AppPanel id="nanoclaw-card" title="NanoClaw">
    <p class="body">
      <StatusMark id="nanoclaw-status" :status="healthy.status" :label="healthy.label" />
    </p>
    <div v-if="!nanoclaw.available" id="nanoclaw-not-answering" class="body grid gap-2">
      <template v-if="nanoclaw.reason === 'not_answering'">
        <p>NanoClaw is not answering.</p>
        <p class="caption text-ink-secondary">
          Its health endpoint on the agent host did not reply to the broker, so NanoClaw is stopped
          or restarting. This card fills in again when it answers.
        </p>
      </template>
      <template v-else>
        <p>Couldn’t read NanoClaw’s health through the broker.</p>
        <p class="caption text-ink-secondary">NanoClaw may be fine; the broker read failed.</p>
      </template>
    </div>
    <FactList v-else>
      <FactItem label="Running for" value-id="nanoclaw-uptime">
        {{
          nanoclaw.uptime_seconds === null ? 'Not known' : durationWords(nanoclaw.uptime_seconds)
        }}
      </FactItem>
      <FactItem label="Channels" value-id="nanoclaw-channels">
        <ul v-if="nanoclaw.channels.length" class="flex flex-wrap gap-x-4 gap-y-1">
          <li v-for="(c, i) in nanoclaw.channels" :key="`${c.name}-${i}`">
            {{ c.name ?? 'unnamed' }}
            <StatusMark
              :status="c.connected === null ? 'unknown' : c.connected ? 'ok' : 'failing'"
              :label="
                c.connected === null ? 'Unknown' : c.connected ? 'Connected' : 'Not connected'
              "
              class="font-normal"
            />
          </li>
        </ul>
        <template v-else>None</template>
      </FactItem>
      <FactItem label="Message loop" value-id="nanoclaw-loop">
        <StatusMark
          :status="
            nanoclaw.message_loop_running === null
              ? 'unknown'
              : nanoclaw.message_loop_running
                ? 'ok'
                : 'failing'
          "
          :label="
            nanoclaw.message_loop_running === null
              ? 'Unknown'
              : nanoclaw.message_loop_running
                ? 'Running'
                : 'Stopped'
          "
          class="font-normal"
        />
      </FactItem>
      <FactItem label="Queue" value-id="nanoclaw-queue">
        {{ known(nanoclaw.queue.active) }} active, {{ known(nanoclaw.queue.waiting) }} waiting
      </FactItem>
      <FactItem label="Sessions" value-id="nanoclaw-sessions"
        >{{ known(nanoclaw.active_session_count) }} active</FactItem
      >
      <FactItem label="Groups" value-id="nanoclaw-groups"
        >{{ known(nanoclaw.registered_group_count) }} registered</FactItem
      >
      <FactItem label="Last message" value-id="nanoclaw-last-message">
        <TimeText
          v-if="nanoclaw.last_message_at"
          :at="nanoclaw.last_message_at"
          :now="now"
          relative
        />
        <template v-else>None</template>
      </FactItem>
      <FactItem label="Tasks" value-id="nanoclaw-tasks">
        {{ known(nanoclaw.tasks.active_count) }} active,
        {{ known(nanoclaw.tasks.paused_count) }} paused<template v-if="nanoclaw.tasks.next_run_at"
          >; next <TimeText :at="nanoclaw.tasks.next_run_at" :now="now"
        /></template>
      </FactItem>
    </FactList>
  </AppPanel>
</template>
