import { describe, expect, it } from 'vitest'
import { overview } from '../../fixtures/api'
import { claudeSentence, nanoclawSentence } from '../overview'
import type { NanoclawHealth } from '../types'

describe('the overview’s answer line', () => {
  it('says each Claude status in words', () => {
    expect(claudeSentence('degraded')).toBe('Claude is answering, with problems.')
    expect(claudeSentence('unknown')).toBe('The console can’t tell whether Claude is answering.')
  })

  it('says each NanoClaw state in words', () => {
    const up = overview().nanoclaw as Extract<NanoclawHealth, { available: true }>
    expect(nanoclawSentence(up)).toBe('NanoClaw is running.')
    expect(nanoclawSentence({ ...up, healthy: false })).toBe(
      'NanoClaw is running, but says it is unhealthy.',
    )
    expect(nanoclawSentence({ available: false, reason: 'not_answering' })).toBe(
      'NanoClaw is not answering.',
    )
    expect(nanoclawSentence({ available: false, reason: 'broker_error' })).toBe(
      'The console couldn’t read NanoClaw’s health.',
    )
  })
})
