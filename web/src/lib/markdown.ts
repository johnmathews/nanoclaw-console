import DOMPurify from 'dompurify'
import { Marked, type Tokens } from 'marked'

/**
 * A task file rendered from Markdown to HTML that is safe to insert. Task files are written by
 * agents inside their containers, so they are untrusted: DOMPurify keeps only the tags below
 * (no images, which would load from wherever the file says, no forms, frames or styles), and
 * links keep only http(s) and mailto targets and never send a referrer.
 */
const TAGS = [
  'a',
  'blockquote',
  'br',
  'code',
  'del',
  'em',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'hr',
  'li',
  'ol',
  'p',
  'pre',
  'strong',
  'table',
  'tbody',
  'td',
  'th',
  'thead',
  'tr',
  'ul',
]

const purify = DOMPurify()
purify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') node.setAttribute('rel', 'noopener noreferrer')
})

/**
 * `headingOffset` moves every heading down that many levels (capped at h6), so a file's `#` sits
 * under the page's own section heading instead of competing with the page's h1.
 */
export function renderMarkdown(source: string, { headingOffset = 0 } = {}): string {
  const marked = new Marked({
    gfm: true,
    walkTokens(token) {
      if (token.type === 'heading') {
        const heading = token as Tokens.Heading
        heading.depth = Math.min(6, heading.depth + headingOffset)
      }
    },
  })
  const html = marked.parse(source, { async: false })
  return purify.sanitize(html, {
    ALLOWED_TAGS: TAGS,
    ALLOWED_ATTR: ['href', 'title'],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
  })
}
