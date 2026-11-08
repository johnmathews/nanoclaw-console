<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/lib/markdown'

/**
 * The MarkdownText card: an agent-written Markdown file, rendered and sanitised (lib/markdown.ts)
 * before it reaches v-html. Headings move down two levels, under the page's section heading.
 */
const props = defineProps<{ source: string }>()
const html = computed(() => renderMarkdown(props.source, { headingOffset: 2 }))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -- sanitised by renderMarkdown (DOMPurify) -->
  <div class="markdown" v-html="html" />
</template>
