/** A response the API refused (any status outside 2xx). */
export class ApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number,
  ) {
    super(`${path} answered ${status}`)
    this.name = 'ApiError'
  }
}

/**
 * GET a JSON document from the console's own API, on the page's origin. The Access cookie rides
 * along by default (same origin), so there is no auth header to add.
 */
export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!response.ok) throw new ApiError(path, response.status)
  return (await response.json()) as T
}

/**
 * What an action's POST answered (architecture.md §4.8): the API's JSON for any status it gave,
 * or `{ result: 'network' }` when nothing came back, and `{ result: 'signed_out' }` for the bare
 * 403 of the Access check (an ended sign-in).
 */
export type ActionAnswer = {
  status: number | null
  result: string
  reason?: string | null
  code?: string | null
  detail?: Record<string, number | string> | null
  acted_result?: string | null
}

/**
 * POST one of the four actions. It sends exactly what the API's CSRF guard asks for: an empty JSON
 * object, `Content-Type: application/json` and `X-Console-Action: 1`. The browser adds `Origin`
 * and `Sec-Fetch-Site: same-origin` itself, and the Access cookie rides along (same origin).
 */
export async function postAction(path: string): Promise<ActionAnswer> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-Console-Action': '1',
      },
      body: '{}',
      credentials: 'same-origin',
    })
  } catch {
    return { status: null, result: 'network' }
  }
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (body && typeof body === 'object' && typeof (body as { result?: unknown }).result === 'string')
    return { ...(body as Omit<ActionAnswer, 'status'>), status: response.status }
  if (response.status === 401 || response.status === 403)
    return { status: response.status, result: 'signed_out' }
  return { status: response.status, result: 'unexpected' }
}
