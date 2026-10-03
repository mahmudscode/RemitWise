import { useCallback, useEffect, useState } from 'react'
import { api, BASE, fmtDate, getToken, setToken } from './api'
import { Avatar, Icon } from './ui'
import Auth from './Auth.jsx'
import Home from './Home.jsx'
import Payments from './Payments.jsx'
import Plan from './Plan.jsx'
import Goals from './Goals.jsx'
import Insights from './Insights.jsx'
import Sender from './Sender.jsx'
import Admin from './Admin.jsx'
import RemittanceModal from './RemittanceModal.jsx'

const NAV = [['home', 'Home'], ['payments', 'Payments'], ['plan', 'Plan'], ['goals', 'Goals'], ['insights', 'Insights']]
const PAGES = { home: Home, payments: Payments, plan: Plan, goals: Goals, insights: Insights }
const ROLE_LABEL = { family: 'Family wallet', sender: 'Sender abroad', admin: 'Administrator' }
const allowed = (role) => (role === 'sender' ? ['sender'] : role === 'admin' ? [...NAV.map((n) => n[0]), 'sender', 'admin'] : NAV.map((n) => n[0]))
const defaultPage = (role) => (role === 'sender' ? 'sender' : role === 'admin' ? 'admin' : 'home')
const hashPage = () => location.hash.replace(/^#\/?/, '').split('/')[0]

export default function App() {
  const [auth, setAuth] = useState({ status: getToken() ? 'loading' : 'out', user: null })
  const [page, setPage] = useState('home')
  const [lang, setLang] = useState('en')
  const [hh, setHh] = useState([])
  const [hid, setHid] = useState('')
  const [state, setState] = useState(null)
  const [err, setErr] = useState('')
  const [tick, setTick] = useState(0)
  const [openAdd, setOpenAdd] = useState(false)
  const [dismissed, setDismissed] = useState(null)
  const [clockOpen, setClockOpen] = useState(false)
  const [retry, setRetry] = useState(0)
  const me = auth.user
  const role = me?.role

  const signedOut = useCallback(() => { setAuth({ status: 'out', user: null }); setHh([]); setHid(''); setState(null); setErr('') }, [])

  // Stay signed in across refreshes and new browser sessions: the token lives in localStorage, the session on the server.
  useEffect(() => {
    if (!getToken()) return
    api('/auth/me').then((d) => setAuth({ status: 'in', user: d.user }))
      .catch((e) => { if (e.network) setAuth({ status: 'error', user: null, msg: e.message }); else { setToken(null); signedOut() } })  // keep the session if the server is only unreachable
  }, [signedOut, retry])
  useEffect(() => { window.addEventListener('rw-unauth', signedOut); return () => window.removeEventListener('rw-unauth', signedOut) }, [signedOut])

  const onAuthed = (user) => { setAuth({ status: 'in', user }); setPage(defaultPage(user.role)); location.hash = `/${defaultPage(user.role)}` }
  const logout = async () => { try { await api('/auth/logout', { method: 'POST' }) } catch { /* already gone */ } setToken(null); signedOut(); location.hash = '' }

  useEffect(() => {
    if (!role) return
    const h = hashPage()
    setPage(allowed(role).includes(h) ? h : defaultPage(role))
    const f = () => { const x = hashPage(); setPage(allowed(role).includes(x) ? x : defaultPage(role)) }
    window.addEventListener('hashchange', f)
    return () => window.removeEventListener('hashchange', f)
  }, [role])
  const go = (p, opts) => { if (!allowed(role).includes(p)) return; if (opts?.add) setOpenAdd(true); location.hash = `/${p}`; setPage(p) }

  useEffect(() => {
    if (auth.status !== 'in') return
    api('/households')
      .then((r) => { setHh(r); setHid(role === 'admin' ? r[0]?.household_id || '' : me.household_id) })
      .catch((e) => setErr(e.message))
  }, [auth.status, role, me])

  const refresh = useCallback(async () => {
    if (!hid) return
    if (role === 'sender') { setState({ sender: true }); setTick((x) => x + 1); return }  // senders never read the family's private state
    try { setState(await api(`/households/${hid}/state`)); setTick((x) => x + 1) } catch (e) { setErr(e.message) }
  }, [hid, role])
  useEffect(() => { refresh() }, [refresh])

  const act = async (fn) => {
    setErr('')
    try { await fn() } catch (e) { setErr(e.message); await refresh(); throw e }
    await refresh()
  }
  const advance = (days, to_arrival = false) => act(() => api(`/households/${hid}/advance`, { method: 'POST', body: { days, to_arrival } })).catch(() => {})
  const person = hh.find((h) => h.household_id === hid)
  const H = {}
  const ctx = { hid, state, tick, lang, H, act, person, go, hh, setHid, me, logout, role }
  const Page = PAGES[page]
  const showModal = state?.pending && dismissed !== state.pending.seq && page !== 'sender' && page !== 'admin'

  if (auth.status === 'loading') return <p className="muted" style={{ padding: 24 }}>Loading…</p>
  if (auth.status === 'error') return <div style={{ padding: 24, maxWidth: 560 }}><div className="error">{auth.msg}</div><p className="muted small" style={{ margin: '10px 0' }}>You are still signed in. Your data is safe on the server.</p><button className="btn primary" onClick={() => { setAuth({ status: 'loading', user: null }); setRetry((x) => x + 1) }}>Try again</button></div>
  if (auth.status === 'out') return <Auth onAuthed={onAuthed} />

  // The demo clock lives in the layout (sidebar on desktop, top of the page on phones) so it never floats over content.
  const clock = state && page !== 'admin' && role !== 'sender' && (
    <div className="clockbox">
      <button className="x row between" style={{ width: '100%', color: '#fff', opacity: 1 }} onClick={() => setClockOpen(!clockOpen)}><span>Demo clock · <b>{fmtDate(state.date)}</b></span><span style={{ marginLeft: 12 }}>{clockOpen ? '–' : '+'}</span></button>
      {clockOpen && <div className="btns"><button className="go" onClick={() => advance(1, true)}>Trigger remittance</button><button onClick={() => advance(1)}>+1 day</button><button onClick={() => advance(7)}>+7 days</button>
        {role === 'admin' && <button onClick={() => go('admin')}>Admin console</button>}
        <button onClick={() => setLang(lang === 'en' ? 'bn' : 'en')}>{lang === 'en' ? 'বাংলা' : 'English'}</button></div>}
    </div>
  )

  return (
    <>
      {err && <div className="error" style={{ margin: 12 }} onClick={() => setErr('')}>{err}</div>}
      {!state && <p className="muted" style={{ padding: 24 }}>{err ? 'Waiting for the API…' : 'Loading…'}</p>}
      {state && page === 'admin' && <Admin {...ctx} />}
      {state && page === 'sender' && <Sender {...ctx} />}
      {state && page !== 'admin' && page !== 'sender' && (
        <div className="shell">
          <aside className="sidebar">
            <div className="brand"><span className="logo">R</span>RemitWise</div>
            {NAV.map(([k, label]) => <button key={k} className={`nav ${page === k ? 'on' : ''}`} onClick={() => go(k)}><Icon name={k} />{label}</button>)}
            <div className="sidefoot">
              {clock}
              {role === 'admin' && <div className="viewas">Previewing a demo household<button className="link" onClick={() => go('sender')}>Preview sender view →</button><button className="link" onClick={() => go('admin')}>Back to admin console →</button></div>}
              {role === 'admin' && <select value={hid} onChange={(e) => setHid(e.target.value)}>{hh.map((h) => <option key={h.household_id} value={h.household_id}>{h.name} · {h.regularity_class}</option>)}</select>}
              <div className="me"><Avatar text={me.name} /><div className="grow"><b>{me.name}</b><small>{ROLE_LABEL[role]}</small></div><button className="link gray" onClick={logout}>Log out</button></div>
            </div>
          </aside>
          <main className="main">
            <div className="only-mobile row between" style={{ marginBottom: 10 }}>
              {role === 'admin' ? <select value={hid} onChange={(e) => setHid(e.target.value)} style={{ width: 'auto' }}>{hh.map((h) => <option key={h.household_id} value={h.household_id}>{h.name} · {h.regularity_class}</option>)}</select> : <span className="small muted">Signed in as <b>{me.name}</b></span>}
              <span>{role === 'admin' && <button className="link" onClick={() => go('admin')}>Admin console</button>}<button className="link gray" onClick={logout}>Log out</button></span>
            </div>
            <div className="only-mobile" style={{ marginBottom: 12 }}>{clock}</div>
            <Page {...ctx} openAdd={openAdd} clearAdd={() => setOpenAdd(false)} />
            <p className="tiny muted" style={{ textAlign: 'center', marginTop: 24 }}>Synthetic data only. No real money or customer data.</p>
          </main>
          <nav className="bottomnav">{NAV.map(([k, label]) => <button key={k} className={page === k ? 'on' : ''} onClick={() => go(k)}><Icon name={k} />{label}</button>)}</nav>
        </div>
      )}
      {showModal && <RemittanceModal {...ctx} onClose={() => setDismissed(state.pending.seq)} />}
    </>
  )
}
