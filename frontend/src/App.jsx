import { useCallback, useEffect, useState } from 'react'
import { api, fmtDate, BASE } from './api'
import Family from './Family.jsx'
import Sender from './Sender.jsx'
import Judge from './Judge.jsx'

const VIEWS = { family: 'Family app', sender: 'Sender view', judge: 'Demo & insights' }

export default function App() {
  const [view, setView] = useState(() => (['family', 'sender', 'judge'].includes(location.hash.slice(1).split('/')[0]) ? location.hash.slice(1).split('/')[0] : 'family'))
  const [lang, setLang] = useState('en')
  const [hh, setHh] = useState([])
  const [hid, setHid] = useState('')
  const [state, setState] = useState(null)
  const [err, setErr] = useState('')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    api('/households', { role: 'admin' })
      .then((r) => { setHh(r); setHid(r[0]?.household_id || '') })
      .catch(() => setErr(BASE
        ? `Cannot reach the API at ${BASE}. Check that the backend is running, its /api/health works, and ALLOWED_ORIGINS includes this site.`
        : 'No backend URL configured. Locally: run ./run.sh api (API on port 8000). On Vercel: set VITE_API_URL to your https backend URL and redeploy.'))
  }, [])

  const role = view === 'family' ? 'family' : view === 'sender' ? 'sender' : 'admin'
  const user = view === 'family' ? hid : view === 'sender' ? `S-${hid}` : ''

  const refresh = useCallback(async () => {
    if (!hid) return
    try { setState(await api(`/households/${hid}/state`, { role: 'admin' })); setTick((x) => x + 1) }
    catch (e) { setErr(e.message) }
  }, [hid])
  useEffect(() => { refresh() }, [refresh])

  const act = async (fn) => {
    setErr('')
    try { await fn() } catch (e) { setErr(e.message); await refresh(); throw e }
    await refresh()
  }
  const advance = (days, to_arrival = false) =>
    act(() => api(`/households/${hid}/advance`, { method: 'POST', role: 'admin', body: { days, to_arrival } })).catch(() => {})
  const person = hh.find((h) => h.household_id === hid)
  const props = { hid, state, refresh, lang, role, user, act, tick, person }

  return (
    <div className="app">
      <header>
        <div className="brand"><span className="logo">R</span><div><b>RemitWise</b><small>AI planner for remittance families</small></div></div>
        <nav className="seg">
          {Object.entries(VIEWS).map(([v, label]) => <button key={v} className={view === v ? 'tab on' : 'tab'} onClick={() => setView(v)}>{label}</button>)}
        </nav>
        <div className="tools">
          <select value={hid} onChange={(e) => setHid(e.target.value)}>
            {hh.map((h) => <option key={h.household_id} value={h.household_id}>{h.name} · {h.regularity_class}</option>)}
          </select>
          <button className="ghost" onClick={() => setLang(lang === 'en' ? 'bn' : 'en')}>{lang === 'en' ? 'বাংলা' : 'English'}</button>
        </div>
      </header>

      {state && (
        <div className="timebar">
          <span>Simulated today: <b>{fmtDate(state.date)}</b></span>
          <span className="spacer" />
          <button className="primary" onClick={() => advance(1, true)}>Trigger remittance</button>
          <button onClick={() => advance(1)}>+1 day</button>
          <button onClick={() => advance(7)}>+7 days</button>
        </div>
      )}
      {err && <div className="error" onClick={() => setErr('')}>{err}</div>}
      <p className="demo-note">Synthetic data only. Demo roles are for illustration, not real authentication.</p>

      {!state ? <p className="muted">{err ? 'Waiting for the API…' : 'Loading…'}</p> : (
        <main>
          {view === 'family' && <Family {...props} />}
          {view === 'sender' && <Sender {...props} />}
          {view === 'judge' && <Judge {...props} />}
        </main>
      )}
    </div>
  )
}
