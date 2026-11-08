import { describe, expect, it } from 'vitest'
import { sourceProblems } from '../sources'

describe('sourceProblems', () => {
  it('is empty when every read answered', () => {
    expect(
      sourceProblems({ broker: { ok: true, errors: {} }, loki: { ok: true, errors: {} } }),
    ).toEqual([])
  })

  it('names each failed read in words, with its code', () => {
    expect(
      sourceProblems({
        broker: { ok: false, errors: { usage: 'timeout', 'tasks-list': 'unavailable' } },
        loki: { ok: false, errors: { claude: 'not_configured' } },
      }),
    ).toEqual([
      { what: 'the quota', why: 'the broker took too long to answer', code: 'timeout' },
      { what: 'the task list', why: 'the broker did not answer', code: 'unavailable' },
      { what: 'Claude’s traffic in Loki', why: 'Loki is not configured', code: 'not_configured' },
    ])
  })

  it('falls back to the read’s own name and the code', () => {
    expect(sourceProblems({ broker: { ok: false, errors: { 'new-verb': 'odd' } } })).toEqual([
      { what: 'new-verb', why: 'it failed', code: 'odd' },
    ])
  })
})

describe('sourceProblems, every code', () => {
  it('words each code the broker and Loki give', () => {
    const errors = {
      'tasks-get': 'protocol_error',
      'task-file': 'unknown_verb',
      'groups-list': 'invalid_params',
      'sessions-list': 'ncl_error',
    }
    expect(
      sourceProblems({
        broker: { ok: false, errors },
        loki: { ok: false, errors: { host_logs: 'bad_response' } },
      }).map((p) => `${p.what}: ${p.why}`),
    ).toEqual([
      'the task’s details: the broker gave an answer the console could not read',
      'the task file: this broker does not offer that read',
      'the group list: the broker refused the request',
      'sessions: NanoClaw refused the request',
      'NanoClaw’s host logs in Loki: Loki gave an answer the console could not read',
    ])
  })
})
