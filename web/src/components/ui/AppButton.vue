<script setup lang="ts">
/**
 * The Button card: primary (`ink` fill, `on-ink` words) for the one action a step exists for,
 * secondary (outlined) for the choices beside it, quiet for the least of them. 44px tall at every
 * width. Busy keeps full colour and sets `aria-busy`; the slot carries the busy words. Only
 * `disabled` fades. Focus is the global solid 2px outline (main.css).
 */
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'quiet'
    type?: 'button' | 'submit'
    busy?: boolean
    disabled?: boolean
  }>(),
  { variant: 'secondary', type: 'button', busy: false, disabled: false },
)
</script>

<template>
  <button
    :type="type"
    :data-variant="variant"
    :disabled="disabled"
    :aria-busy="busy ? 'true' : undefined"
    class="body inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-md border px-4 font-semibold whitespace-nowrap select-none disabled:cursor-not-allowed disabled:opacity-40 aria-busy:cursor-progress motion-safe:transition-colors motion-safe:duration-120"
    :class="{
      'border-ink bg-ink text-on-ink hover:not-disabled:bg-ink-hover': variant === 'primary',
      'border-control-border bg-transparent text-ink hover:not-disabled:bg-tile':
        variant === 'secondary',
      'border-transparent bg-transparent text-ink hover:not-disabled:bg-tile': variant === 'quiet',
    }"
  >
    <slot />
  </button>
</template>
