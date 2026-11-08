// Runs before first paint, so a dark OS setting doesn't flash the light theme while the app loads,
// and keeps following the setting while the page is open. A plain file rather than an inline
// script, so a strict CSP (script-src 'self') can serve it.
{
  const query = window.matchMedia('(prefers-color-scheme: dark)')
  const apply = () => document.documentElement.classList.toggle('dark', query.matches)
  apply()
  query.addEventListener('change', apply)
}
