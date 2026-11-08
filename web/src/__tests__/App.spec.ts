import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../App.vue'

function mountWith(fetchImpl: () => Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl))
  return mount(App, { global: { plugins: [createPinia()] } })
}

describe('the placeholder page', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('names the product in its one heading', () => {
    const wrapper = mountWith(() => new Promise(() => {}))
    const headings = wrapper.findAll('h1')
    expect(headings).toHaveLength(1)
    expect(headings[0]!.text()).toBe('NanoClaw console')
  })

  it('says it is loading until the API answers', () => {
    const wrapper = mountWith(() => new Promise(() => {}))
    expect(wrapper.text()).toContain('Asking the console’s API')
  })

  it('says the API answered', async () => {
    const wrapper = mountWith(async () => new Response('{"status":"scaffold"}'))
    await flushPromises()
    expect(wrapper.find('[data-testid="api-status"]').text()).toContain(
      'The console’s API answered',
    )
  })

  it('says what to do when the API cannot be reached', async () => {
    const wrapper = mountWith(async () => new Response('{}', { status: 502 }))
    await flushPromises()
    const status = wrapper.find('[data-testid="api-status"]')
    expect(status.attributes('role')).toBe('alert')
    expect(status.text()).toContain(
      'Couldn’t reach the console’s API. Reload the page to try again.',
    )
  })
})
