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
