<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronLeft } from '@lucide/vue'
import ActionBar from '@/components/ActionBar.vue'
import FactItem from '@/components/ui/FactItem.vue'
import FactList from '@/components/ui/FactList.vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import MarkdownText from '@/components/MarkdownText.vue'
import PageStatus from '@/components/PageStatus.vue'
import TaskStatus from '@/components/TaskStatus.vue'
import TimeText from '@/components/TimeText.vue'
import { useApi } from '@/composables/useApi'
import { usePageTitle } from '@/composables/usePageTitle'
import { taskActions, taskConfirmation, type ActionOutcome } from '@/lib/actions'
import { OVERDUE_WORDS, runsWords, taskName } from '@/lib/tasks'
import { formatWhen } from '@/lib/time'
import type { TaskDetail } from '@/lib/types'

/**
 * One task (question 3 in full): what it will do (its task file), its whole prompt, its schedule
 * and its recent runs. Its header carries release 2's actions: pause or resume by its status, and
 * run now, each behind a ConfirmDialog; the answer shows under the header and the page refreshes.
 */
const route = useRoute()
const id = computed(() => String(route.params.id))
const { data, error, checkedAt, refresh } = useApi<TaskDetail>(
  computed(() => `/api/tasks/${encodeURIComponent(id.value)}`),
)

const actions = computed(() => {
  const t = task.value
  if (!t) return []
  return taskActions(t).map((action) => ({
    slot: action === 'run' ? 'run' : 'toggle',
    confirmation: taskConfirmation(action, t, checkedAt.value),
  }))
})
const outcome = ref<ActionOutcome | null>(null)
watch(id, () => (outcome.value = null))
function answered(result: ActionOutcome): void {
  outcome.value = result
  void refresh()
}

const task = computed(() => data.value?.task ?? null)
const missing = computed(() => !data.value && error.value?.status === 404)
const brokerDown = computed(() =>
  !data.value && error.value?.status === 503
    ? {
        lead: 'Couldn’t reach the broker, so this task can’t be shown.',
        text: 'It retries every 30 seconds.',
      }
    : null,
)
const title = computed(() =>
  task.value ? taskName(task.value) : missing.value ? 'Task not found' : 'Task',
)
usePageTitle(() => title.value)

const fileName = computed(() => (task.value?.task_file ? `tasks/${task.value.task_file}` : null))
const fileReadFailed = computed(() => 'task-file' in (data.value?.sources.broker.errors ?? {}))

/** F9: the plan's exact words, when it last ran, and what follows the catch-up run. */
const overdueSentence = computed(() => {
  const t = task.value
  if (!t) return ''
  const then = `fter that one run it runs ${t.schedule.words ? t.schedule.words.charAt(0).toLowerCase() + t.schedule.words.slice(1) : 'on its schedule'}.`
  return t.last_run_at
    ? `${OVERDUE_WORDS}. It last ran ${formatWhen(t.last_run_at, checkedAt.value)}; a${then}`
    : `${OVERDUE_WORDS}. A${then}`
})
</script>

<template>
  <div id="task-page" class="grid gap-10">
    <header class="grid gap-3">
      <p class="caption">
        <RouterLink
          id="task-back"
          to="/tasks"
          class="inline-flex min-h-11 items-center gap-1 underline underline-offset-[3px] hover:decoration-2"
        >
          <ChevronLeft aria-hidden="true" :size="16" :stroke-width="1.5" />All tasks
        </RouterLink>
      </p>
      <div class="flex flex-wrap items-start justify-between gap-4">
        <h1 class="display min-w-0 break-words">{{ title }}</h1>
        <ActionBar :items="actions" @answered="answered" />
      </div>
      <template v-if="task">
        <div class="body flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <TaskStatus id="task-status" :task="task" brief />
          <code class="caption font-mono text-ink-secondary">{{ task.id }}</code>
        </div>
      </template>
      <p v-else-if="missing" id="task-missing" class="body-large">
        There is no task {{ id }}. It may have finished or been removed.
        <RouterLink to="/tasks" class="underline underline-offset-[3px]">See every task</RouterLink
        >.
      </p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <InlineMessage
        v-if="task && outcome"
        id="action-result"
        :tone="outcome.tone"
        :data-tone="outcome.tone"
      >
        <p class="body">{{ outcome.text }}</p>
      </InlineMessage>
      <PageStatus
        v-if="!missing"
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="data?.sources ?? null"
        :failure="brokerDown"
      />
    </header>

    <template v-if="task">
      <InlineMessage v-if="task.overdue_on_resume" id="task-overdue" tone="caution">
        <p class="body">{{ overdueSentence }}</p>
      </InlineMessage>

      <section id="task-file" aria-labelledby="task-file-title" class="grid gap-3">
        <h2 id="task-file-title" class="title-1">What it will do</h2>
        <template v-if="data?.task_file">
          <p id="task-file-name" class="caption font-mono text-ink-secondary">{{ fileName }}</p>
          <InlineMessage v-if="data.task_file.truncated" tone="caution">
            The file is longer than the console reads (256 KiB); this is its start.
          </InlineMessage>
          <div
            id="task-file-content"
            class="max-w-prose rounded-lg border border-line bg-panel p-4 sm:p-6"
          >
            <MarkdownText :source="data.task_file.content" />
          </div>
        </template>
        <p v-else-if="!fileName" class="body">
          The prompt names no task file, so the prompt below is everything it does.
        </p>
        <InlineMessage v-else-if="fileReadFailed" tone="error">
          Couldn’t read {{ fileName }}. The prompt below says where it should be.
        </InlineMessage>
        <p v-else class="body">
          {{ fileName }} isn’t in the group’s folder, so the agent will find nothing to follow.
        </p>
      </section>

      <section id="task-prompt-section" aria-labelledby="task-prompt-title" class="grid gap-3">
        <h2 id="task-prompt-title" class="title-1">Prompt</h2>
        <blockquote
          id="task-prompt"
          class="note max-w-prose border-l-2 border-line pl-4 break-words whitespace-pre-wrap"
        >
          {{ task.prompt ?? 'No prompt' }}
        </blockquote>
        <InlineMessage v-if="task.has_script" id="task-script" tone="info">
          This task also runs a script. The console doesn’t show scripts.
        </InlineMessage>
      </section>

      <section id="task-runs-section" aria-labelledby="task-runs-title" class="grid gap-4">
        <h2 id="task-runs-title" class="title-1">Runs</h2>
        <FactList>
          <FactItem label="Completed runs" value-id="task-runs">{{
            task.completed_runs ?? task.runs ?? 'Not known'
          }}</FactItem>
          <FactItem label="Failed runs" value-id="task-failed-runs">{{
            task.failed_runs ?? 'Not known'
          }}</FactItem>
          <FactItem label="Retries of this run" value-id="task-tries">{{
            task.tries ?? 'Not known'
          }}</FactItem>
          <FactItem label="Last run" value-id="task-last-run">
            <TimeText v-if="task.last_run_at" :at="task.last_run_at" :now="checkedAt" relative />
            <template v-else>Never</template>
          </FactItem>
          <FactItem label="Next run" value-id="task-next-run">
            <TimeText v-if="task.next_run_at" :at="task.next_run_at" :now="checkedAt" relative />
            <template v-else>{{
              task.status === 'paused' ? 'Not while paused' : 'Not scheduled'
            }}</template>
          </FactItem>
          <FactItem label="Series started" value-id="task-series-started">
            <TimeText
              v-if="task.series_started_at"
              :at="task.series_started_at"
              :now="checkedAt"
              relative
            />
            <template v-else>Not known (the id carries no time)</template>
          </FactItem>
          <FactItem label="In short">{{ runsWords(task) }}</FactItem>
        </FactList>
        <h3 class="title-2">Recent run log</h3>
        <ol
          v-if="task.recent_log.length"
          id="task-run-log"
          class="caption grid gap-1 font-mono break-words"
        >
          <li v-for="(line, i) in task.recent_log" :key="i">{{ line }}</li>
        </ol>
        <p v-else id="task-run-log-empty" class="body text-ink-secondary">No run log yet.</p>
      </section>

      <section id="task-details" aria-labelledby="task-details-title" class="grid gap-4">
        <h2 id="task-details-title" class="title-1">Details</h2>
        <FactList>
          <FactItem label="Group" value-id="task-group">
            {{ task.group.name ?? 'Not in the group list' }}
            <code v-if="task.group.id" class="font-mono text-ink-secondary">{{
              task.group.id
            }}</code>
          </FactItem>
          <FactItem label="Schedule" value-id="task-schedule">
            {{ task.schedule.words ?? 'Not readable' }}
            <code v-if="task.schedule.cron" class="font-mono text-ink-secondary">{{
              task.schedule.cron
            }}</code
            >, in {{ task.schedule.timezone }}
          </FactItem>
          <FactItem label="Session" value-id="task-session">
            <code v-if="task.session_id" class="font-mono">{{ task.session_id }}</code>
            <template v-else>None</template>
          </FactItem>
          <FactItem label="This occurrence" value-id="task-row-id">
            <code v-if="task.row_id" class="font-mono">{{ task.row_id }}</code>
            <template v-else>Not known</template>
          </FactItem>
        </FactList>
      </section>
    </template>
  </div>
</template>
