import { describe, expect, it } from 'vitest'
import { renderMarkdown } from '../markdown'

describe('renderMarkdown', () => {
  it('renders headings, lists, emphasis and code', () => {
    const html = renderMarkdown('# Title\n\n1. **One**\n2. `two`\n')
    expect(html).toContain('<h1>Title</h1>')
    expect(html).toContain('<strong>One</strong>')
    expect(html).toContain('<code>two</code>')
  })

  it('moves headings down under the page’s own, never below h6', () => {
    const html = renderMarkdown('# One\n\n##### Five\n', { headingOffset: 2 })
    expect(html).toContain('<h3>One</h3>')
    expect(html).toContain('<h6>Five</h6>')
  })

  it('removes scripts, event handlers and images', () => {
    const html = renderMarkdown(
      '<script>alert(1)</script>\n\n<p onclick="alert(2)">x</p>\n\n<img src="https://t.example/p.gif">\n\n![a](https://t.example/q.gif)\n',
    )
    expect(html).not.toMatch(/<script|onclick|<img|t\.example/)
    expect(html).toContain('<p>x</p>')
  })

  it('removes javascript: links and keeps http links, opened without a referrer', () => {
    const html = renderMarkdown('[bad](javascript:alert(1)) [good](https://example.com/x)')
    expect(html).not.toContain('javascript:')
    expect(html).toContain('href="https://example.com/x"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('drops forms, iframes and styles', () => {
    const html = renderMarkdown(
      '<form action="/x"><input></form><iframe src="https://x"></iframe><style>*{}</style><p style="color:red">y</p>',
    )
    expect(html).not.toMatch(/<form|<input|<iframe|<style|style=/)
  })
})
