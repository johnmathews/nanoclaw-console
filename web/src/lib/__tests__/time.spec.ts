import { describe, expect, it } from 'vitest'
import { durationWords, exactTime, formatWhen, relativeWords } from '../time'

// 2026-11-08 15:30 in Amsterdam (CET, UTC+1), a Sunday.
const NOW = new Date('2026-11-08T14:30:00.000Z')

describe('formatWhen, in Europe/Amsterdam with the zone named', () => {
  it('says today', () => {
    expect(formatWhen('2026-11-08T14:28:12.000Z', NOW)).toBe('today at 15:28 CET')
  })

  it('says tomorrow and yesterday', () => {
    expect(formatWhen('2026-11-09T08:00:00.000Z', NOW)).toBe('tomorrow at 09:00 CET')
    expect(formatWhen('2026-11-07T16:00:41.000Z', NOW)).toBe('yesterday at 17:00 CET')
  })

  it('names the weekday within the coming week', () => {
    expect(formatWhen('2026-11-12T08:00:00.000Z', NOW)).toBe('Thursday at 09:00 CET')
  })

  it('names the day and month, in summer time, earlier in the year', () => {
    expect(formatWhen('2026-05-26T07:03:00.000Z', NOW)).toBe('26 May at 09:03 CEST')
  })

  it('adds the year when it is another year', () => {
    expect(formatWhen('2025-12-31T22:30:00.000Z', NOW)).toBe('31 December 2025 at 23:30 CET')
  })

  it('uses the Amsterdam date, not the UTC date, for today', () => {
    // 23:30 UTC on the 8th is 00:30 on the 9th in Amsterdam.
    expect(formatWhen('2026-11-08T23:30:00.000Z', NOW)).toBe('tomorrow at 00:30 CET')
  })
})

describe('relativeWords', () => {
  it('says just now under a minute', () => {
    expect(relativeWords('2026-11-08T14:29:31.000Z', NOW)).toBe('just now')
  })

  it('writes small numbers as words', () => {
    expect(relativeWords('2026-11-08T14:28:00.000Z', NOW)).toBe('two minutes ago')
    expect(relativeWords('2026-11-08T14:37:00.000Z', NOW)).toBe('in seven minutes')
    expect(relativeWords('2026-11-08T16:30:00.000Z', NOW)).toBe('in two hours')
    expect(relativeWords('2026-11-08T13:29:00.000Z', NOW)).toBe('an hour ago')
  })

  it('uses figures above ten', () => {
    expect(relativeWords('2026-11-08T14:00:00.000Z', NOW)).toBe('30 minutes ago')
  })

  it('counts days, then months, then years', () => {
    expect(relativeWords('2026-11-05T14:30:00.000Z', NOW)).toBe('three days ago')
    expect(relativeWords('2026-05-26T07:03:00.000Z', NOW)).toBe('five months ago')
    expect(relativeWords('2024-11-01T00:00:00.000Z', NOW)).toBe('two years ago')
  })
})

describe('durationWords', () => {
  it('says how long, in the largest whole unit', () => {
    expect(durationWords(72739)).toBe('20 hours')
    expect(durationWords(45 * 60)).toBe('45 minutes')
    expect(durationWords(3 * 86400 + 5)).toBe('three days')
    expect(durationWords(30)).toBe('less than a minute')
  })
})

describe('exactTime', () => {
  it('gives the full date and time with seconds and the zone', () => {
    expect(exactTime('2026-11-08T14:28:12.000Z')).toBe('Sunday 8 November 2026, 15:28:12 CET')
  })

  it('passes through what it cannot read', () => {
    expect(exactTime('not a time')).toBe('not a time')
    expect(formatWhen('not a time', NOW)).toBe('not a time')
    expect(relativeWords('not a time', NOW)).toBe('')
  })
})

describe('shortWhen and the edges', () => {
  it('drops "today at" for today only', async () => {
    const { shortWhen } = await import('../time')
    expect(shortWhen('2026-11-08T14:28:12.000Z', NOW)).toBe('15:28 CET')
    expect(shortWhen('2026-11-07T14:28:12.000Z', NOW)).toBe('yesterday at 15:28 CET')
    expect(shortWhen('nonsense', NOW)).toBe('nonsense')
  })

  it('says a single unit with an article, and uses figures for long durations', () => {
    expect(relativeWords('2026-11-07T14:30:00.000Z', NOW)).toBe('a day ago')
    expect(relativeWords('2027-11-08T14:30:00.000Z', NOW)).toBe('in a year')
    expect(durationWords(86_400)).toBe('one day')
    expect(durationWords(20 * 86_400)).toBe('20 days')
  })
})
