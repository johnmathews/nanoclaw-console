<script setup lang="ts">
import { nextTick, watch } from 'vue'
import {
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogOverlay,
  AlertDialogPortal,
  AlertDialogRoot,
  AlertDialogTitle,
} from 'reka-ui'
import AppButton from './AppButton.vue'
import InlineMessage from './InlineMessage.vue'

/**
 * The ConfirmDialog card: a small modal question before an action on NanoClaw. Built on Reka UI's
 * AlertDialog (role="alertdialog", aria-modal, the focus trap and the inert page). It names the
 * thing and its state now, says what will happen, and carries the action's caution line; a
 * failure shows above the buttons and keeps the dialog open. Focus starts on Cancel; Escape
 * cancels, except while the action runs; on closing, focus returns to the control that asked.
 */
const props = withDefaults(
  defineProps<{
    /** The question, naming the thing: "Pause documentation-summary?". */
    title: string
    /** The thing's state now: "Now: paused. Its next run was due 27 May at 09:03 CEST." */
    state: string
    /** What happens, then what stays. */
    effect: string
    /** The action's caution line, when it has one ("A run spends tokens; …"). */
    warning?: string | null
    /** The verb from the title, on the primary button. Never "OK" or "Yes". */
    verb: string
    /** The verb while it runs: "Pausing…". */
    busyVerb: string
    busy?: boolean
    /** What went wrong and what to do; the dialog stays open. */
    error?: string | null
  }>(),
  { warning: null, busy: false, error: null },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()
const open = defineModel<boolean>('open', { default: false })

// Opened from code, so remember the control that asked and give focus back to it on closing.
let opener: HTMLElement | null = null
watch(open, (isOpen) => {
  if (isOpen) opener = document.activeElement as HTMLElement | null
})

function onOpenChange(next: boolean): void {
  if (next || props.busy) return // nothing closes it while the action runs
  open.value = false
  emit('cancel')
}

function onCloseAutoFocus(event: Event): void {
  event.preventDefault()
  const target = opener
  void nextTick(() => target?.focus())
}

function confirm(): void {
  if (!props.busy) emit('confirm')
}
</script>

<template>
  <AlertDialogRoot :open="open" @update:open="onOpenChange">
    <AlertDialogPortal>
      <AlertDialogOverlay
        data-slot="confirm-dialog-scrim"
        class="fixed inset-0 z-50 bg-scrim opacity-40 motion-safe:transition-opacity motion-safe:duration-120 print:hidden"
      />
      <!-- No id on the content or the title: Reka's own ids are what aria-labelledby and
           aria-describedby point at. -->
      <AlertDialogContent
        data-slot="confirm-dialog"
        aria-modal="true"
        class="fixed inset-0 z-50 m-auto h-fit max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-lg border border-line bg-panel p-4 text-ink shadow-overlay sm:p-6 print:hidden"
        @close-auto-focus="onCloseAutoFocus"
      >
        <AlertDialogTitle as="h2" data-slot="confirm-title" class="title-2 break-words">{{
          title
        }}</AlertDialogTitle>
        <AlertDialogDescription as="div" class="mt-3 grid gap-2">
          <p id="confirm-state" class="body">{{ state }}</p>
          <p id="confirm-effect" class="body">{{ effect }}</p>
        </AlertDialogDescription>
        <InlineMessage v-if="warning" id="confirm-warning" tone="caution" class="mt-4">
          <p class="body">{{ warning }}</p>
        </InlineMessage>
        <InlineMessage v-if="error" id="confirm-error" tone="error" class="mt-4">
          <p class="body">{{ error }}</p>
        </InlineMessage>
        <p class="caption mt-4 text-ink-secondary">
          The console records this in its audit log with your sign-in.
        </p>
        <div class="mt-6 flex flex-wrap justify-end gap-3">
          <AlertDialogCancel as-child>
            <AppButton id="confirm-cancel" variant="secondary">Cancel</AppButton>
          </AlertDialogCancel>
          <AppButton id="confirm-act" variant="primary" :busy="busy" @click="confirm">{{
            busy ? busyVerb : verb
          }}</AppButton>
        </div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
