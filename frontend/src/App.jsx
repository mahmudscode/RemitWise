import { useCallback, useEffect, useState } from 'react'
import { api, fmtDate } from './api'
import { T } from './i18n'
import Family from './Family.jsx'
import Sender from './Sender.jsx'
import Judge from './Judge.jsx'

export default function App() {
  const [view, setView] = useState('family')
  const [lang, setLang] = useState('en')
  const [hh, setHh] = useState([])
  const [hid, setHid] = useState('')
  const [state, setState] = useState(null)
  const [err, setErr] = useState('')
  const [tick, setTick] = useState(0)
  const t = T[lang]

  useEffect(() => {
    api('/households', { role: 'admin' })
      .then((r) => { setHh(r); setHid(r[0]?.household_id || '') })
      .catch(() => setErr('Cannot reach the API on port 8000. Start it with ./run.sh api (and run ./run.sh build once if you have not).'))
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
    try { await fn(); await refresh() } catch (e) { setErr(e.message) }
  }
  const advance = (days, to_arrival = false) =>
    act(() => api(`/households/${hid}/advance`, { method: 'POST', role: 'admin', body: { days, to_arrival } }))

  const person = hh.find((h) => h.household_id === hid)

  return (
    <div className="app">
      <header>
        <div className="brand"><span className="logo">R</span><div><b>RemitWise</b><small>AI planner for remittance families</small></div></div>
        <nav>
          {['family', 'sender', 'judge'].map((v) => (
            <button key={v} className={view === v ? 'tab on' : 'tab'} onClick={() => setView(v)}>{t[v]}</button>
          ))}
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
          <span>{t.today}: <b>{fmtDate(state.date)}</b> <small>(simulated, day {state.day})</small></span>
          <span className="spacer" />
          <button onClick={() => advance(1)}>{t.nextDay}</button>
          <button onClick={() => advance(7)}>{t.week}</button>
          <button className="primary" onClick={() => advance(1, true)}>{t.toArrival}</button>
        </div>
      )}
      {err && <div className="error" onClick={() => setErr('')}>{err}</div>}
      <p className="demo-note">Synthetic data only. Demo roles are for illustration, not real authentication.</p>

      {!state ? <p className="muted">{err ? 'Waiting for the API…' : 'Loading…'}</p> : (
        <main>
          {view === 'family' && <Family {...{ hid, state, refresh, lang, t, role, user, act, tick, person }} />}
          {view === 'sender' && <Sender {...{ hid, state, refresh, lang, t, role, user, act, tick, person }} />}
          {view === 'judge' && <Judge {...{ hid, state, refresh, lang, t, act, tick, person }} />}
        </main>
      )}
    </div>
  )
}
