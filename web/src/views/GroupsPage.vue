<script setup lang="ts">
import { computed, ref } from 'vue'
import AccessMark from '@/components/ui/AccessMark.vue'
import FactItem from '@/components/ui/FactItem.vue'
import FactList from '@/components/ui/FactList.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import PageStatus from '@/components/PageStatus.vue'
import PolicyValue from '@/components/PolicyValue.vue'
import TimeText from '@/components/TimeText.vue'
import { useApi } from '@/composables/useApi'
import { useHashTarget } from '@/composables/useHashTarget'
import { usePageTitle } from '@/composables/usePageTitle'
import {
  channelLabel,
  domId,
  engageWords,
  groupName,
  groupsAnswer,
  mountSummary,
} from '@/lib/groups'
import type { Group, GroupsView } from '@/lib/types'

/**
 * Every agent group and its channels (question 2): a card per group with what matters at a
 * glance (RecordList card, as cards), each linked to the group's own page, then the channels
 * wired to no group. Group cards sit two across from 1024px.
 */
usePageTitle(() => 'Groups and channels')
const { data, error, checkedAt } = useApi<GroupsView>(ref('/api/groups'))
useHashTarget(computed(() => data.value !== null))

const answer = computed(() => (data.value ? groupsAnswer(data.value) : null))

/**
 * A messaging group wired to several groups is drawn on each card, but only its first gets the
 * `channel-<id>` anchor a problem's link points at, so the id stays unique.
 */
const anchors = computed(() => {
  const seen = new Set<string>()
  const out = new Map<string, string>()
  for (const g of data.value?.groups ?? [])
    for (const c of g.channels) {
      const mg = c.messaging_group_id
      if (mg && !seen.has(mg)) {
        seen.add(mg)
        out.set(`${g.id} ${mg}`, `channel-${domId(mg)}`)
      }
    }
  return out
})

function modelWords(g: Group): string {
  if (!g.config) return 'Couldn’t read'
  const model = g.config.model ?? 'Model not set'
  return `${model}, ${g.config.provider ? `provider ${g.config.provider}` : 'provider not set'}`
}

function tasksWords(g: Group): string {
  const { total, paused, overdue_on_resume: overdue } = g.tasks
  if (!total) return 'None'
  let s = `${total} ${total === 1 ? 'task' : 'tasks'}`
  if (paused) {
    s += `, ${paused} paused`
    if (overdue === paused)
      s +=
        paused === 1
          ? ' (would run once straight away if resumed)'
          : ' (each would run once straight away if resumed)'
    else if (overdue) s += ` (${overdue} would run once straight away if resumed)`
  }
  return s
}

function hasWriteMount(g: Group): boolean {
  return g.config?.mounts.some((m) => !m.read_only) ?? false
}
</script>

<template>
  <div id="groups-page" class="grid gap-10">
    <header class="grid gap-3">
      <h1 class="display">Groups and channels</h1>
      <p v-if="answer" id="groups-answer" class="body-large">{{ answer }}</p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <PageStatus
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="data?.sources ?? null"
      />
    </header>

    <template v-if="data">
      <section
        v-if="data.groups.length"
        id="groups-section"
        aria-labelledby="groups-title"
        class="grid gap-4"
      >
        <h2 id="groups-title" class="title-1">Groups</h2>
        <ul id="groups-list" class="grid items-start gap-6 lg:grid-cols-2">
          <li
            v-for="g in data.groups"
            :id="`group-card-${g.id}`"
            :key="g.id"
            class="grid content-start gap-4 rounded-lg border border-line bg-panel p-4 shadow-overlay sm:p-6"
          >
            <div class="grid gap-1">
              <h3 class="title-2 break-words">
                <RouterLink
                  :to="`/groups/${g.id}`"
                  class="underline underline-offset-[3px] hover:decoration-2"
                >
                  {{ groupName(g) }}
                </RouterLink>
              </h3>
              <code class="caption font-mono break-all text-ink-secondary">{{
                g.folder ?? g.id
              }}</code>
            </div>
            <FactList>
              <FactItem label="Model" :value-id="`group-${g.id}-model`">{{
                modelWords(g)
              }}</FactItem>
              <FactItem label="Channels" :value-id="`group-${g.id}-channels`">
                <ul v-if="g.channels.length" class="grid gap-1">
                  <li
                    v-for="(c, i) in g.channels"
                    :id="anchors.get(`${g.id} ${c.messaging_group_id}`)"
                    :key="c.wiring_id ?? i"
                  >
                    {{ channelLabel(c) }}: {{ engageWords(c).toLowerCase() }}
                  </li>
                </ul>
                <template v-else>None wired</template>
              </FactItem>
              <FactItem label="MCP servers" :value-id="`group-${g.id}-mcp`">
                <template v-if="!g.config">Couldn’t read</template>
                <template v-else-if="g.config.mcp_servers.length">{{
                  g.config.mcp_servers.map((s) => s.name).join(', ')
                }}</template>
                <template v-else>None</template>
              </FactItem>
              <FactItem label="Mounts" :value-id="`group-${g.id}-mounts`">
                <template v-if="!g.config">Couldn’t read</template>
                <AccessMark
                  v-else-if="hasWriteMount(g)"
                  read-write
                  :write-label="mountSummary(g.config.mounts)"
                />
                <template v-else>{{ mountSummary(g.config.mounts) }}</template>
              </FactItem>
              <FactItem label="Tasks" :value-id="`group-${g.id}-tasks`">{{
                tasksWords(g)
              }}</FactItem>
              <FactItem label="Sessions" :value-id="`group-${g.id}-sessions`"
                >{{ g.sessions.total }}, {{ g.sessions.running }} running</FactItem
              >
            </FactList>
          </li>
        </ul>
      </section>

      <section id="unwired-channels" aria-labelledby="unwired-title" class="grid gap-3">
        <h2 id="unwired-title" class="title-1">Channels wired to no group</h2>
        <template v-if="data.unwired_channels.length">
          <p class="body">Messages from these channels reach no agent.</p>
          <ul class="divide-y divide-line border-y border-line">
            <li
              v-for="(c, i) in data.unwired_channels"
              :id="c.id ? `channel-${domId(c.id)}` : `unwired-${i}`"
              :key="c.id ?? i"
              class="grid gap-3 py-4"
            >
              <h3 class="body font-semibold break-words">
                {{ channelLabel(c) }}
                <span class="caption font-normal text-ink-secondary">{{
                  c.channel_type ?? 'unknown type'
                }}</span>
              </h3>
              <FactList>
                <FactItem label="Platform id">
                  <code class="font-mono break-all">{{ c.platform_id ?? 'Not known' }}</code>
                </FactItem>
                <FactItem
                  label="Unknown senders"
                  :value-id="c.id ? `channel-${domId(c.id)}-unknown` : undefined"
                >
                  <PolicyValue axis="unknown_sender_policy" :value="c.unknown_sender_policy" />
                </FactItem>
              </FactList>
              <InlineMessage v-if="c.denied_at" tone="caution">
                Denied <TimeText :at="c.denied_at" :now="checkedAt" />
              </InlineMessage>
            </li>
          </ul>
        </template>
        <p
          v-else-if="'messaging-groups-list' in data.sources.broker.errors"
          class="body text-ink-secondary"
        >
          Couldn’t read the channels.
        </p>
        <p v-else class="body text-ink-secondary">Every channel is wired to a group.</p>
      </section>
    </template>
  </div>
</template>
