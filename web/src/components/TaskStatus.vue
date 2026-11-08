<script setup lang="ts">
import { computed } from 'vue'
import InlineMessage from '@/components/ui/InlineMessage.vue'
import { statusWords } from '@/lib/tasks'
import type { Task } from '@/lib/types'

/**
 * A task's status in words (TaskList card). A paused task that would run at once on resume is a
 * caution, in caution-ink with its icon and the plan's exact words (F9); any other status is
 * plain text, paused ones in ink-secondary.
 */
const props = defineProps<{
  task: Task
  /** Just "Paused" for an overdue task, where the page states the full warning beside it. */
  brief?: boolean
}>()
const caution = computed(() => props.task.overdue_on_resume && !props.brief)
const words = computed(() =>
  props.task.overdue_on_resume && props.brief ? 'Paused' : statusWords(props.task),
)
</script>

<template>
  <InlineMessage v-if="caution" tone="caution">{{ words }}</InlineMessage>
  <span v-else :class="task.status === 'paused' ? 'text-ink-secondary' : ''">{{ words }}</span>
</template>
