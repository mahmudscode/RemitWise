import { useCallback, useEffect, useState } from 'react'
import { api, BASE, fmtDate, getToken, setToken } from './api'
import { Avatar, Icon, LangToggle } from './ui'
import { getLang, setLang as setLangModule, t } from './i18n'
import Auth from './Auth.jsx'
import Home from './Home.jsx'
import Payments from './Payments.jsx'
import Plan from './Plan.jsx'
import Goals from './Goals.jsx'
import Insights from './Insights.jsx'
import Sender from './Sender.jsx'
import Admin from './Admin.jsx'
import RemittanceModal from './RemittanceModal.jsx'
import { GuidedBar } from './Guided.jsx'

const NAV = [['home', 'Home'], ['payments', 'Payments'], ['plan', 'Plan'], ['goals', 'Goals'], ['insights', 'Insights']]
const PAGES = { home: Home, payments: Payments, plan: Plan, goals: Goals, insights: Insights }
const ROLE_LABEL = { family: 'Family wallet', sender: 'Sender abroad', admin: 'Administrator' }
const allowed = (role) => (role === 'sender' ? ['sender'] : role === 'admin' ? [...NAV.map((n) => n[0]), 'sender', 'admin'] : NAV.map((n) => n[0]))
const defaultPage = (role) => (role === 'sender' ? 'sender' : role === 'admin' ? 'admin' : 'home')
const hashPage = () => location.hash.replace(/^#\/?/, '').split('/')[0]

// Free hosts put the API to sleep when idle. Ping /api/health as soon as the app opens and show a friendly screen
// (with a retry) until it answers, instead of a page full of errors.
function useServerReady() {
  const [ready, setReady] = useState(false)
  const [slow, setSlow] = useState(false)
  const [attempts, setAttempts] = useState(0)
  const [round, setRound] = useState(0)
  useEffect(() => {
    let dead = false, timer
    const showSlow = setTimeout(() => { if (!dead) setSlow(true) }, 1000)
    const ping = async () => {
      if (dead) return
      setAttempts((n) => n + 1)
      try {
        const r = await fetch(`${BASE}/api/health`)
        if (r.ok) { if (!dead) setReady(true); return }
      } catch { /* server still starting */ }
      if (!dead) timer = setTimeout(ping, 2500)
    }
    ping()
    return () => { dead = true; clearTimeout(timer); clearTimeout(showSlow) }
  }, [round])
  return { ready, slow, attempts, retry: () => { setAttempts(0); setRound((x) => x + 1) } }
}

function Waking({ attempts, retry, lang, changeLang }) {
  return (
    <div className="waking" role="status">
      <div className="inner">
        <div className="spinner" />
        <h1 style={{ fontSize: 26 }}>{t('Waking up the server…')}</h1>
        <p style={{ opacity: .9 }}>{t('The free demo server sleeps when idle. The first load can take up to a minute. We will open the app as soon as it is ready.')}</p>
        {attempts > 2 && <p className="small" style={{ opacity: .8 }}>{t('Still trying… (attempt {n})', { n: attempts })}</p>}
        <button className="btn" onClick={retry}>{t('Retry now')}</button>
        <LangToggle lang={lang} onChange={changeLang} dark />
      </div>
    </div>
  )
}

export default function App() {
  const gate = useServerReady()
  const [lang, setLangState] = useState(getLang())
  const changeLang = (l) => { setLangModule(l); setLangState(l) }
  if (!gate.ready) return gate.slow ? <Waking attempts={gate.attempts} retry={gate.retry} lang={lang} changeLang={changeLang} /> : null
  return <AppInner lang={lang} changeLang={changeLang} />
}

function AppInner({ lang, changeLang }) {
  const [auth, setAuth] = useState({ status: getToken() ? 'loading' : 'out', user: null })
  const [page, setPage] = useState('home')
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
  const [gLast, setGLast] = useState(0)
  const H = {}
  const guided = {
    last: gLast, setLast: setGLast,
    run: (n) => act(async () => { const r = await api(`/households/${hid}/demo/step`, { method: 'POST', body: { step: n } }); setGLast(n); go(r.open) }).catch(() => {}),
  }
  const ctx = { hid, state, tick, lang, changeLang, guided, H, act, person, go, hh, setHid, me, logout, role }
  const Page = PAGES[page]
  const showModal = state?.pending && dismissed !== state.pending.seq && page !== 'sender' && page !== 'admin'

  if (auth.status === 'loading') return <p className="muted" style={{ padding: 24 }}>{t('Loading…')}</p>
  if (auth.status === 'error') return <div style={{ padding: 24, maxWidth: 560 }}><div className="error">{auth.msg}</div><p className="muted small" style={{ margin: '10px 0' }}>{t('You are still signed in. Your data is safe on the server.')}</p><button className="btn primary" onClick={() => { setAuth({ status: 'loading', user: null }); setRetry((x) => x + 1) }}>{t('Try again')}</button></div>
  if (auth.status === 'out') return <Auth onAuthed={onAuthed} lang={lang} changeLang={changeLang} />

  // The demo clock lives in the layout (sidebar on desktop, top of the page on phones) so it never floats over content.
  const clock = state && page !== 'admin' && role !== 'sender' && (
    <div className="clockbox">
      <button className="x row between" style={{ width: '100%', color: '#fff', opacity: 1 }} onClick={() => setClockOpen(!clockOpen)}><span>{t('Demo clock')} · <b>{fmtDate(state.date)}</b></span><span style={{ marginLeft: 12 }}>{clockOpen ? '–' : '+'}</span></button>
      {clockOpen && <div className="btns"><button className="go" onClick={() => advance(1, true)}>{t('Trigger remittance')}</button><button onClick={() => advance(1)}>{t('+1 day')}</button><button onClick={() => advance(7)}>{t('+7 days')}</button>
        {role === 'admin' && <button onClick={() => go('admin')}>{t('Admin console')}</button>}</div>}
    </div>
  )

  return (
    <>
      {err && <div className="error" style={{ margin: 12 }} onClick={() => setErr('')}>{err}</div>}
      {!state && <p className="muted" style={{ padding: 24 }}>{err ? t('Waiting for the API…') : t('Loading…')}</p>}
      {state && page === 'admin' && <Admin {...ctx} />}
      {state && page === 'sender' && <Sender {...ctx} />}
      {state && page !== 'admin' && page !== 'sender' && (
        <div className="shell">
          <aside className="sidebar">
            <div style={{ marginBottom: 22 }}><div className="brand" style={{ marginBottom: 2 }}><span className="logo">R</span>RemitWise</div><div className="forupay" style={{ paddingLeft: 44 }}><b>{t('for upay')}</b></div></div>
            <div style={{ margin: '-10px 0 14px' }}><LangToggle lang={lang} onChange={changeLang} /></div>
            {NAV.map(([k, label]) => <button key={k} className={`nav ${page === k ? 'on' : ''}`} onClick={() => go(k)}><Icon name={k} />{t(label)}</button>)}
            <div className="sidefoot">
              {clock}
              {role === 'admin' && <div className="viewas">{t('Previewing a demo household')}<button className="link" onClick={() => go('sender')}>{t('Preview sender view →')}</button><button className="link" onClick={() => go('admin')}>{t('Back to admin console →')}</button></div>}
              {role === 'admin' && <select value={hid} onChange={(e) => setHid(e.target.value)}>{hh.map((h) => <option key={h.household_id} value={h.household_id}>{h.name} · {h.regularity_class}</option>)}</select>}
              {(() => {
                const displayName = (role === 'admin' && person?.name) ? person.name : me.name
                const displayRole = t((role === 'admin' && page !== 'admin') ? 'Family wallet' : ROLE_LABEL[role])
                return (
                  <div className="me">
                    <Avatar text={displayName} />
                    <div className="grow"><b>{displayName}</b><small>{displayRole}</small></div>
                    <button className="link gray" onClick={logout}>{t('Log out')}</button>
                  </div>
                )
              })()}
            </div>
          </aside>
          <main className="main">
            <div className="only-mobile row between" style={{ marginBottom: 10 }}>
              {role === 'admin' ? <select value={hid} onChange={(e) => setHid(e.target.value)} style={{ width: 'auto' }}>{hh.map((h) => <option key={h.household_id} value={h.household_id}>{h.name} · {h.regularity_class}</option>)}</select> : <span className="small muted">{t('Signed in as')} <b>{me.name}</b></span>}
              <span><LangToggle lang={lang} onChange={changeLang} />{role === 'admin' && <button className="link" onClick={() => go('admin')}>{t('Admin console')}</button>}<button className="link gray" onClick={logout}>{t('Log out')}</button></span>
            </div>
            <div className="only-mobile" style={{ marginBottom: 12 }}>{clock}</div>
            <Page key={hid} {...ctx} openAdd={openAdd} clearAdd={() => setOpenAdd(false)} />
            <p className="tiny muted" style={{ textAlign: 'center', marginTop: 24 }}>{t('Synthetic data only. No real money or customer data.')}</p>
          </main>
          <nav className="bottomnav">{NAV.map(([k, label]) => <button key={k} className={page === k ? 'on' : ''} onClick={() => go(k)}><Icon name={k} />{t(label)}</button>)}</nav>
        </div>
      )}
      {state && role === 'admin' && page !== 'admin' && page !== 'sender' && <GuidedBar guided={guided} go={go} />}
      {showModal && <RemittanceModal {...ctx} onClose={() => setDismissed(state.pending.seq)} />}
    </>
  )
}
