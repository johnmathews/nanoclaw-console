import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import pluginVitest from '@vitest/eslint-plugin'
import pluginOxlint from 'eslint-plugin-oxlint'
import pluginTailwind from 'eslint-plugin-better-tailwindcss'
import pluginVueA11y from 'eslint-plugin-vuejs-accessibility'
import skipFormatting from 'eslint-config-prettier/flat'

// To allow more languages other than `ts` in `.vue` files, uncomment the following lines:
// import { configureVueProject } from '@vue/eslint-config-typescript'
// configureVueProject({ scriptLangs: ['ts', 'tsx'] })
// More info at https://github.com/vuejs/eslint-config-typescript/#advanced-setup

// Colour utilities that take a colour value. A role class (bg-canvas, text-pen) is the only way in.
const COLOUR_UTILITY =
  '(?:bg|text|border(?:-[trblxyse])?|outline|ring|ring-offset|divide|fill|stroke|decoration|accent|caret|shadow|inset-shadow|from|via|to|placeholder)'

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{vue,ts,mts,tsx}'],
  },

  globalIgnores([
    '**/dist/**',
    '**/dist-ssr/**',
    '**/coverage/**',
    'playwright-report/**',
    'test-results/**',
  ]),

  ...pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,

  {
    name: 'app/vue-conventions',
    files: ['src/**/*.vue'],
    rules: {
      // Styling lives in Tailwind classes on the design system's roles (docs/development.md).
      'vue/no-restricted-block': [
        'error',
        { element: 'style', message: 'No <style> blocks: use Tailwind classes on the roles.' },
      ],
    },
  },

  // Template accessibility (eslint-plugin-vuejs-accessibility's recommended rules). Only the
  // rules: its flat preset also swaps in its own vue-eslint-parser without the TS options.
  {
    name: 'app/vue-a11y',
    files: ['src/**/*.vue'],
    plugins: { 'vuejs-accessibility': pluginVueA11y },
    rules: {
      ...pluginVueA11y.configs.recommended.rules,
      // A label needs `for` or a nested control, not both (the default asks for both).
      'vuejs-accessibility/label-has-for': ['error', { required: { some: ['nesting', 'id'] } }],
    },
  },

  // Tailwind classes, read against the real stylesheet (src/styles/main.css): the default palette
  // is switched off there, so `bg-red-500` generates nothing at build time and fails here. The
  // type classes (caption, title-2…) are found in tokens.css's `components` layer.
  {
    name: 'app/tailwind',
    files: ['src/**/*.{vue,ts}'],
    ignores: ['src/**/__tests__/**'],
    plugins: { 'better-tailwindcss': pluginTailwind },
    settings: {
      'better-tailwindcss': {
        entryPoint: 'src/styles/main.css',
        detectComponentClasses: true,
      },
    },
    rules: {
      'better-tailwindcss/no-unknown-classes': 'error',
      'better-tailwindcss/no-conflicting-classes': 'error',
      'better-tailwindcss/no-duplicate-classes': 'error',
      'better-tailwindcss/no-deprecated-classes': 'error',
      'better-tailwindcss/no-restricted-classes': [
        'error',
        {
          restrict: [
            {
              // bg-[#fff], text-[rgb(0_0_0)], border-[color:oklch(…)], [color:#000]…
              pattern:
                '^.*\\[(?:[a-z-]+:)?(?:#[0-9a-fA-F]{3,8}|(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\\().*$',
              message: 'Arbitrary colour "$0": use a role (bg-canvas, text-ink-secondary, …).',
            },
            {
              // bg-[var(--canvas)] bypasses the role utilities.
              pattern: `^(?:.*:)?${COLOUR_UTILITY}-\\[(?:color:)?var\\(.*$`,
              message:
                'Colour from a raw variable "$0": use the role utility (bg-canvas, text-pen, …).',
            },
          ],
        },
      ],
    },
  },

  {
    ...pluginVitest.configs.recommended,
    files: ['src/**/__tests__/*'],
  },

  ...pluginOxlint.buildFromOxlintConfigFile('.oxlintrc.json'),

  skipFormatting,
)
