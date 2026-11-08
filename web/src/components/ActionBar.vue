<script setup lang="ts">
import { computed, ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { outcomeWords, type ActionOutcome, type Confirmation } from '@/lib/actions'
import { postAction } from '@/lib/api'

/**
 * A page's action buttons (release 2, architecture.md §5.8): each opens the ConfirmDialog with its
 * words; Confirm posts the action once. An answer that closes the dialog (done, already in that
 * state, not found) is handed to the page, which shows it and refreshes; any other answer stays in
 * the dialog as its error. Buttons are keyed by `slot`, so Pause turning into Resume after a
 * refresh is the same button and keeps focus.
 */
const props = defineProps<{ items: { slot: string; confirmation: Confirmation }[] }>()
const emit = defineEmits<{ answered: [outcome: ActionOutcome, confirmation: Confirmation] }>()

const open = ref(false)
const active = ref<Confirmation | null>(null)
const busy = ref(false)
const error = ref<string | null>(null)

const shown = computed(() => active.value ?? props.items[0]?.confirmation ?? null)

function ask(confirmation: Confirmation): void {
  active.value = confirmation
  error.value = null
  open.value = true
}

async function confirm(): Promise<void> {
  const asked = active.value
  if (!asked || busy.value) return
  busy.value = true
  error.value = null
  const answer = await postAction(asked.path)
  busy.value = false
  const outcome = outcomeWords(asked.action, answer)
  if (!outcome.closes) {
    error.value = outcome.text
    return
  }
  open.value = false
  emit('answered', outcome, asked)
}

function cancel(): void {
  error.value = null
}
</script>

<template>
  <div v-if="items.length" class="flex flex-wrap gap-3" role="group" aria-label="Actions">
    <AppButton
      v-for="item in items"
      :id="`action-${item.slot}`"
      :key="item.slot"
      :data-action="item.confirmation.action"
      variant="secondary"
      aria-haspopup="dialog"
      @click="ask(item.confirmation)"
      >{{ item.confirmation.verb }}</AppButton
    >
  </div>
  <ConfirmDialog
    v-if="shown"
    v-model:open="open"
    :title="shown.title"
    :state="shown.state"
    :effect="shown.effect"
    :warning="shown.warning"
    :verb="shown.verb"
    :busy-verb="shown.busyVerb"
    :busy="busy"
    :error="error"
    @confirm="confirm"
    @cancel="cancel"
  />
</template>
