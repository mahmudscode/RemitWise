// Demo auth: role + user headers (NOT real authentication).
// Local dev uses the Vite proxy (empty base). On Vercel set VITE_API_URL to the backend's https URL.
export const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export async function api(path, { method = 'GET', body, role = 'family', user = '' } = {}) {
  const res = await fetch(`${BASE}/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Role': role, 'X-User': user },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`)
  return data
}

export const taka = (n) => (n == null ? '–' : '৳' + Math.round(n).toLocaleString('en-US'))
export const pct = (x) => `${Math.round(x * 100)}%`
export const fmtDate = (s) => {
  if (!s) return '–'
  const d = new Date(s + 'T00:00:00')
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
