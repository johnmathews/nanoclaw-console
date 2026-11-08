/**
 * Times as John reads them: in Europe/Amsterdam, the zone named ("today at 09:03 CET"), with a
 * relative phrase where it helps ("in two hours"). The API sends UTC ISO; nothing here assumes
 * the browser's own zone.
 */
export const DISPLAY_TIMEZONE = 'Europe/Amsterdam'

const LOCALE = 'en-GB'
const WORDS = [
  'zero',
  'one',
  'two',
  'three',
  'four',
  'five',
  'six',
  'seven',
  'eight',
  'nine',
  'ten',
]

/** Small numbers as words, figures above ten (voice.md). */
export function numberWords(n: number): string {
  return n >= 0 && n <= 10 ? WORDS[n]! : String(n)
}

function parse(iso: string): Date | null {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date
}

function parts(date: Date, options: Intl.DateTimeFormatOptions): Record<string, string> {
  const out: Record<string, string> = {}
  const format = new Intl.DateTimeFormat(LOCALE, { timeZone: DISPLAY_TIMEZONE, ...options })
  for (const part of format.formatToParts(date)) out[part.type] = part.value
  return out
}

/** The calendar day in Amsterdam, as a day number that subtracts cleanly. */
function dayNumber(date: Date): number {
  const p = parts(date, { year: 'numeric', month: '2-digit', day: '2-digit' })
  return Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day)) / 86_400_000
}

function clock(date: Date): string {
  const p = parts(date, {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZoneName: 'short',
  })
  return `${p.hour}:${p.minute} ${p.timeZoneName}`
}

/** "today at 15:28 CET", "tomorrow at 09:00 CET", "Thursday at …", "26 May at 09:03 CEST". */
export function formatWhen(iso: string, now: Date): string {
  const date = parse(iso)
  if (date === null) return iso
  const days = dayNumber(date) - dayNumber(now)
  const time = clock(date)
  if (days === 0) return `today at ${time}`
  if (days === 1) return `tomorrow at ${time}`
  if (days === -1) return `yesterday at ${time}`
  const p = parts(date, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
  if (days > 1 && days < 7) return `${p.weekday} at ${time}`
  const sameYear = p.year === parts(now, { year: 'numeric' }).year
  return `${p.day} ${p.month}${sameYear ? '' : ` ${p.year}`} at ${time}`
}

/** Just the clock when it is today ("15:30 CET"), else as formatWhen. */
export function shortWhen(iso: string, now: Date): string {
  const date = parse(iso)
  if (date === null) return iso
  return dayNumber(date) === dayNumber(now) ? clock(date) : formatWhen(iso, now)
}

const UNITS: [name: string, seconds: number][] = [
  ['year', 365.25 * 86_400],
  ['month', 30.44 * 86_400],
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
]

/**
 * The largest unit there is (nearly) one of, rounded: 1m48s is "two minutes", 57 minutes "an
 * hour", 365 days "a year" (not "12 months").
 */
function amount(seconds: number): string | null {
  for (const [name, size] of UNITS) {
    if (seconds >= size * 0.95) {
      const n = Math.max(1, Math.round(seconds / size))
      if (n === 1) return name === 'hour' ? 'an hour' : `a ${name}`
      return `${numberWords(n)} ${name}s`
    }
  }
  return null
}

/** "just now", "two minutes ago", "in two hours", "five months ago"; empty if unreadable. */
export function relativeWords(iso: string, now: Date): string {
  const date = parse(iso)
  if (date === null) return ''
  const seconds = (date.getTime() - now.getTime()) / 1000
  const words = amount(Math.abs(seconds))
  if (words === null) return 'just now'
  return seconds > 0 ? `in ${words}` : `${words} ago`
}

/** How long something has lasted, in its largest whole unit: "20 hours", "three days". */
export function durationWords(seconds: number): string {
  for (const [name, size] of UNITS) {
    const n = Math.floor(seconds / size)
    if (n >= 1)
      return `${n === 1 ? 'one' : n > 10 ? String(n) : numberWords(n)} ${name}${n === 1 ? '' : 's'}`
  }
  return 'less than a minute'
}

/** The full date and time with seconds and zone, for a tooltip: "Sunday 8 November 2026, 15:28:12 CET". */
export function exactTime(iso: string): string {
  const date = parse(iso)
  if (date === null) return iso
  const p = parts(date, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
    timeZoneName: 'short',
  })
  return `${p.weekday} ${p.day} ${p.month} ${p.year}, ${p.hour}:${p.minute}:${p.second} ${p.timeZoneName}`
}
