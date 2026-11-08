import { numberWords } from './time'

/** "Three groups", "One channel": a count at the start of a sentence (voice.md). */
export function countWords(n: number, one: string, many: string = `${one}s`): string {
  const w = numberWords(n)
  return `${w.charAt(0).toUpperCase()}${w.slice(1)} ${n === 1 ? one : many}`
}

/** A code from NanoClaw as words: `decline_notify` → "Decline notify". */
export function humanise(code: string): string {
  const words = code.replace(/[_-]+/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** "a, b and c". */
export function listWords(items: string[]): string {
  if (items.length < 2) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}
