// Runs synchronously in <head> before first paint so the page never flashes the wrong theme.
// Kept as an external file so CSP script-src 'self' needs no inline script.
(function () {
  let mode = 'dark' // default before sign-in; the account's choice replaces it
  try {
    const saved = localStorage.getItem('mindgrid.theme')
    if (saved === 'light' || saved === 'dark' || saved === 'system') mode = saved
  } catch {
    // storage blocked: keep the default
  }
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const dark = mode === 'dark' || (mode === 'system' && prefersDark)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  document.documentElement.dataset.themeMode = mode
})()
