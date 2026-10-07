// Real accounts: a bearer token is kept in localStorage so a refresh or a new browser session stays signed in.
// Local dev uses the Vite proxy (empty base). On Vercel set VITE_API_URL to the backend's https URL.
export const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

const TOKEN_KEY = 'rw_token'
export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) } catch { return null } }
export const setToken = (t) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* private mode */ } }

// `role` / `user` options are accepted for older call sites but ignored: the server decides from the token.
export async function api(path, { method = 'GET', body, token: tokenOverride } = {}) {
  const token = tokenOverride ?? getToken()
  let res
  try {
    res = await fetch(`${BASE}/api${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    const e = new Error(BASE
      ? `Cannot reach the API at ${BASE}. Check that the backend is running, its /api/health works, and ALLOWED_ORIGINS includes this site.`
      : `Could not reach ${location.origin}/api. Locally: make sure ./run.sh api is running (port 8000) and open the app from http://localhost:5173, then reload this page. On Vercel: set VITE_API_URL to your https backend URL and redeploy.`)
    e.network = true
    throw e
  }
  // 502/503/504 from OUR API carry a JSON message (email not set up, server busy ...): show it. Without one, the proxy or host is down.
  const peek = [502, 503, 504].includes(res.status) ? await res.clone().json().catch(() => null) : null
  if ([502, 503, 504].includes(res.status) && !(peek && typeof peek.detail === 'string')) {  // the proxy or host could not reach the backend
    const e = new Error(BASE
      ? 'The backend is not responding yet. If it is on a free host it may be waking up; wait a minute and try again.'
      : 'The backend is not running. In a terminal, run ./run.sh api (it listens on port 8000), then try again.')
    e.network = true
    throw e
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/login') && !path.startsWith('/auth/register')) {
      setToken(null)
      window.dispatchEvent(new Event('rw-unauth'))
    }
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(' ') : data.detail
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return data
}

export const taka = (n) => (n == null ? '–' : '৳' + Math.round(n).toLocaleString('en-IN'))
export const pct = (x) => `${Math.round(x * 100)}%`
import { locale } from './i18n'
export const fmtDate = (s) => {
  if (!s) return '–'
  const d = new Date(s + 'T00:00:00')
  return d.toLocaleDateString(locale(), { day: 'numeric', month: 'short' })
}
export const longDate = (s) => new Date(s + 'T00:00:00').toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' })
export const monthName = (s) => new Date(s + 'T00:00:00').toLocaleDateString(locale(), { month: 'long' })
