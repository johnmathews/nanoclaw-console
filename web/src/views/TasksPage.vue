<script setup lang="ts">
import { computed, ref } from 'vue'
import FactItem from '@/components/ui/FactItem.vue'
import FactList from '@/components/ui/FactList.vue'
import PageStatus from '@/components/PageStatus.vue'
import TaskStatus from '@/components/TaskStatus.vue'
import TimeText from '@/components/TimeText.vue'
import { useApi } from '@/composables/useApi'
import { usePageTitle } from '@/composables/usePageTitle'
import { runsWords, taskName } from '@/lib/tasks'
import { formatWhen, numberWords, relativeWords } from '@/lib/time'
import type { Task, TaskList } from '@/lib/types'

/**
 * Every scheduled task (question 3): the TaskList card. A table from 1024px, a card per task
 * below it, both from the same rows; only one is ever displayed.
 */
usePageTitle(() => 'Scheduled tasks')
const { data, error, checkedAt } = useApi<TaskList>(ref('/api/tasks'))

function capital(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

const answer = computed(() => {
  const list = data.value
  if (!list) return null
  if (!list.tasks.length)
    return 'tasks-list' in list.sources.broker.errors
      ? 'Couldn’t read the task list.'
      : 'No scheduled tasks.'
  const n = list.tasks.length
  const parts = [`${capital(numberWords(n))} ${n === 1 ? 'task' : 'tasks'}.`]
  const overdue = list.tasks.filter((t) => t.overdue_on_resume).length
  const paused = list.tasks.filter((t) => t.status === 'paused').length
  if (paused) {
    let s = `${capital(numberWords(paused))} ${paused === 1 ? 'is' : 'are'} paused`
    if (overdue === paused)
      s +=
        paused === 1
          ? ', and would run once straight away if resumed'
          : ', and each would run once straight away if resumed'
    else if (overdue) s += `; ${numberWords(overdue)} would run once straight away if resumed`
    parts.push(`${s}.`)
  }
  const next = list.tasks.find((t) => t.next_run_at)
  if (next?.next_run_at)
    parts.push(
      `Next: ${taskName(next)}, ${formatWhen(next.next_run_at, checkedAt.value)} (${relativeWords(next.next_run_at, checkedAt.value)}).`,
    )
  return parts.join(' ')
})

function groupName(task: Task): string {
  return task.group.name ?? 'Not in the group list'
}

function nextWords(task: Task): string | null {
  if (task.next_run_at) return null
  return task.status === 'paused' ? 'Not while paused' : 'Not scheduled'
}
</script>

<template>
  <div id="tasks-page" class="grid gap-8">
    <header class="grid gap-3">
      <h1 class="display">Scheduled tasks</h1>
      <p v-if="answer" id="tasks-answer" class="body-large">{{ answer }}</p>
      <p v-else-if="!error" class="body-large text-ink-secondary">Asking the console’s API…</p>
      <PageStatus
        :generated-at="data?.generated_at ?? null"
        :checked-at="checkedAt"
        :error="error"
        :sources="data?.sources ?? null"
      />
    </header>

    <template v-if="data?.tasks.length">
      <table id="tasks-table" class="hidden w-full border-collapse text-left lg:table">
        <caption class="sr-only">
          Scheduled tasks, by next run; paused tasks last
        </caption>
        <thead>
          <tr class="border-b border-line">
            <th
              v-for="h in ['Task', 'Group', 'Schedule', 'Next run', 'Last run', 'Runs', 'Status']"
              :key="h"
              scope="col"
              class="label py-2 pr-4 align-bottom"
            >
              {{ h }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="task in data.tasks"
            :id="`task-row-${task.id}`"
            :key="task.id"
            class="border-b border-line align-top"
          >
            <th scope="row" data-col="task" class="caption max-w-64 py-3 pr-4 font-normal">
              <RouterLink
                :to="`/tasks/${task.id}`"
                class="body font-semibold underline underline-offset-[3px] hover:decoration-2"
              >
                {{ taskName(task) }}
              </RouterLink>
            </th>
            <td
              data-col="group"
              class="caption py-3 pr-4"
              :class="task.group.name ? '' : 'text-ink-secondary'"
            >
              {{ groupName(task) }}
            </td>
            <td data-col="schedule" class="caption py-3 pr-4">
              {{ task.schedule.words ?? 'Not readable' }}
              <code v-if="task.schedule.cron" class="block font-mono text-ink-secondary">{{
                task.schedule.cron
              }}</code>
            </td>
            <td data-col="next" class="caption py-3 pr-4">
              <TimeText
                v-if="task.next_run_at"
                :at="task.next_run_at"
                :now="checkedAt"
                relative
                stacked
              />
              <span v-else class="text-ink-secondary">{{ nextWords(task) }}</span>
            </td>
            <td data-col="last" class="caption py-3 pr-4">
              <TimeText
                v-if="task.last_run_at"
                :at="task.last_run_at"
                :now="checkedAt"
                relative
                stacked
              />
              <span v-else class="text-ink-secondary">Never</span>
            </td>
            <td data-col="runs" class="caption py-3 pr-4">{{ runsWords(task) }}</td>
            <td data-col="status" class="caption max-w-56 py-3"><TaskStatus :task="task" /></td>
          </tr>
        </tbody>
      </table>

      <ul id="tasks-cards" class="grid gap-4 lg:hidden">
        <li
          v-for="task in data.tasks"
          :id="`task-card-${task.id}`"
          :key="task.id"
          class="grid gap-3 rounded-lg border border-line bg-panel p-4"
        >
          <h2 class="body font-semibold break-words">
            <RouterLink
              :to="`/tasks/${task.id}`"
              class="underline underline-offset-[3px] hover:decoration-2"
            >
              {{ taskName(task) }}
            </RouterLink>
          </h2>
          <div class="caption"><TaskStatus :task="task" /></div>
          <FactList>
            <FactItem label="Group">{{ groupName(task) }}</FactItem>
            <FactItem label="Schedule">
              {{ task.schedule.words ?? 'Not readable' }}
              <code v-if="task.schedule.cron" class="font-mono text-ink-secondary"
                >({{ task.schedule.cron }})</code
              >
            </FactItem>
            <FactItem label="Next run">
              <TimeText v-if="task.next_run_at" :at="task.next_run_at" :now="checkedAt" relative />
              <template v-else>{{ nextWords(task) }}</template>
            </FactItem>
            <FactItem label="Last run">
              <TimeText v-if="task.last_run_at" :at="task.last_run_at" :now="checkedAt" relative />
              <template v-else>Never</template>
            </FactItem>
            <FactItem label="Runs">{{ runsWords(task) }}</FactItem>
          </FactList>
        </li>
      </ul>
    </template>
  </div>
</template>
