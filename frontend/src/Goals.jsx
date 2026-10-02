import { useEffect, useRef, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { AI, Bar, Modal, Toggle } from './ui'

export default function Goals({ hid, state, H, act, tick, person, me }) {
  const [copied, setCopied] = useState(false)
  const [consent, setConsent] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [addFor, setAddFor] = useState(null)
  const [amt, setAmt] = useState('')
  const [form, setForm] = useState({ name: '', target: '', days: 240 })
  const [sug, setSug] = useState(null)
  const [hint, setHint] = useState(null)
  const [msg, setMsg] = useState('')
  const timer = useRef(null)

  useEffect(() => {
    api(`/households/${hid}/consent`, H).then(setConsent).catch(() => {})
    api(`/households/${hid}/goals/suggest`, { ...H, method: 'POST', body: { target: 1000, days: 30 } }).then(setHint).catch(() => {})
    // eslint-disable-next-line
  }, [hid, tick])
  useEffect(() => {
    clearTimeout(timer.current)
    if (!form.target || +form.target <= 0) { setSug(null); return }
    timer.current = setTimeout(() => api(`/households/${hid}/goals/suggest`, { ...H, method: 'POST', body: { target: +form.target, days: +form.days } }).then(setSug).catch(() => setSug(null)), 300)
    // eslint-disable-next-line
  }, [form.target, form.days, hid])

  const saved = state.goals.reduce((a, g) => a + g.current, 0)
  const planned = state.goals.reduce((a, g) => a + (g.pace.per_month || 0), 0)
  const shared = state.goals.filter((g) => g.shared).length
  const tone = (g) => (g.pace.on_track === false ? 'amber' : g.pct >= 50 ? 'green' : '')
  const create = async (e) => {
    e.preventDefault(); setMsg('')
    await act(async () => {
      const r = await api(`/households/${hid}/goals`, { ...H, method: 'POST', body: { name: form.name, target: +form.target, days: +form.days, priority: 2 } })
      setMsg(r.feasible ? `Needs about ${taka(r.per_transfer_needed)} per transfer.` : r.note)
      setForm({ name: '', target: '', days: 240 }); setSug(null); setShowNew(false)
    }).catch(() => {})
  }

  return (
    <div className="stackv">
      <div className="pagehead">
        <div><h1>Goals</h1><p><span className="only-mobile">Saving together with {person?.sender_name}</span><span className="only-desktop">Saving together, step by step</span></p></div>
        <button className="btn primary" onClick={() => setShowNew(true)}>+ New goal</button>
      </div>

      <div className="grid3 only-desktop">
        <section className="card blue"><p className="bal-label">Saved toward goals</p><p className="bal-big" style={{ fontSize: 34 }}>{taka(saved)}</p><p className="small" style={{ opacity: .9 }}>across {state.goals.length} goal{state.goals.length === 1 ? '' : 's'}</p></section>
        <section className="card tile"><small>Planned each month</small><b>{planned ? taka(planned) : '–'}</b><span className="foot">at your recent pace</span></section>
        <section className="card tile"><small>Shared with {person?.sender_name}</small><b>{shared} goal{shared === 1 ? '' : 's'}</b><span className="foot">progress only</span></section>
      </div>

      <div className="grid3">
        {state.goals.map((g) => {
          const p = g.pace
          return (
            <section className="card" key={g.id}>
              <div className="row between"><h2>{g.name}</h2><b className={p.on_track === false ? 'txt-amber' : g.pct >= 50 ? 'txt-green' : 'txt-blue'}>{Math.round(g.pct)}%</b></div>
              <p className="muted small" style={{ margin: '4px 0' }}>{taka(g.current)} of {taka(g.target)}</p>
              <Bar pct={g.pct} tone={tone(g)} />
              <div className="row only-desktop between small" style={{ marginTop: 6 }}><span className="muted">Target</span><b>{fmtDate(p.target_date)}</b></div>
              <div className="row only-desktop between small"><span className="muted">Monthly plan</span><b>{taka(p.required_per_month)} / month</b></div>
              <div className="row between wrap small" style={{ margin: '8px 0', gap: 6 }}>
                <b className={p.on_track === false ? 'txt-amber' : p.on_track ? 'txt-green' : 'muted'} style={{ fontWeight: 600 }}>
                  {p.on_track === false ? `Behind · add ${taka(p.catch_up)}/month to catch up` : p.on_track ? `On track · at this pace, ${Math.max(1, Math.round(p.months || 1))} month${Math.max(1, Math.round(p.months || 1)) === 1 ? '' : 's'}` : p.text}
                </b>
                <AI label="AI estimate" title="How this is estimated" why={<p>This uses your last few contributions to this goal and how often transfers usually arrive. It is an estimate and changes as your transfers change.</p>} />
              </div>
              <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                <Toggle checked={g.shared} label={g.shared ? `Shared with ${person?.sender_name}` : 'Private to family'} onChange={(on) => act(() => api(`/households/${hid}/goals/${g.id}/share`, { ...H, method: 'POST', body: { shared: on } }))} />
              </div>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn block" onClick={() => { setAddFor(g); setAmt('') }}>Add money</button>
                <button className="link gray" onClick={() => act(() => api(`/households/${hid}/goals/${g.id}`, { ...H, method: 'DELETE' }))}>Remove</button>
              </div>
            </section>
          )
        })}
      </div>

      {hint && hint.suggested_monthly > 0 && <section className="card info small">Thinking of a new goal? Based on your forecast, about <b>{taka(hint.suggested_monthly)}</b> a month is realistic without risking bills.</section>}
      {msg && <p className="small muted">{msg}</p>}

      <section className="card">
        <h2>Sharing with {person?.sender_name}</h2>
        {me?.role === 'family' && me.invite_code && (
          <div className="invite" style={{ margin: '10px 0' }}>
            <div className="grow"><small className="muted">Invite your sender: they create a Sender account with this code</small><br /><code>{me.invite_code}</code></div>
            <button className="btn sm" onClick={() => { navigator.clipboard?.writeText(me.invite_code); setCopied(true); setTimeout(() => setCopied(false), 1500) }}>{copied ? 'Copied' : 'Copy'}</button>
          </div>
        )}
        <p className="small muted" style={{ margin: '4px 0 10px' }}>{person?.sender_name} sees goal progress only, never your transactions, unless you choose to share more. You can change this any time, and you can say no to any request.</p>
        {consent && (<>
          <p className="small">Sender link: {consent.sender_accepted ? 'accepted ✓' : 'waiting for the sender to accept'}</p>
          <div className="stackv" style={{ gap: 10, marginTop: 8 }}>
            {[['goal_progress', 'Goal progress (the goals switched on above)'], ['savings_total', 'Total savings'], ['bills_status', 'Bills & EMI status, and a suggested send-by date']].map(([k, label]) => (
              <Toggle key={k} checked={consent.scopes[k] === 'granted'} label={<>{label}{consent.scopes[k] === 'requested' && <em className="txt-amber"> · {person?.sender_name} asked to see this</em>}</>}
                onChange={(on) => act(() => api(`/households/${hid}/consent`, { ...H, method: 'POST', body: { scope: k, state: on ? 'granted' : 'revoked' } }))} />
            ))}
          </div>
          <p className="tiny muted" style={{ marginTop: 8 }}>Spending details are not shared in this demo.</p>
        </>)}
      </section>

      {showNew && <Modal title="New goal" onClose={() => setShowNew(false)}>
        <form className="form" onSubmit={create}>
          <div><label>Goal name</label><input placeholder="e.g. Education" maxLength={40} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
          <div className="row"><div className="grow"><label>Target ৳</label><input type="number" min="1" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} required /></div>
            <div className="grow"><label>Days to deadline</label><input type="number" min="14" value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} /></div></div>
          {sug && <div className="suggest"><b>Suggested: {taka(sug.suggested_monthly)} a month</b> <AI label="Estimate" why={<p>{sug.explanation} Your goal needs about {taka(sug.needed_monthly)} a month for this deadline.</p>} /><br />
            <small className="muted">{sug.months_at_suggested ? `About ${sug.months_at_suggested} months at that pace.` : 'No spare money is expected right now.'} {sug.realistic ? '' : 'This deadline looks tight; consider a longer one.'}</small></div>}
          <button className="btn primary block">Create goal</button>
        </form>
      </Modal>}
      {addFor && <Modal title={`Add money to ${addFor.name}`} onClose={() => setAddFor(null)}>
        <form className="form" onSubmit={(e) => { e.preventDefault(); act(() => api(`/households/${hid}/goals/${addFor.id}/add_money`, { ...H, method: 'POST', body: { amount: +amt } })).then(() => setAddFor(null)).catch(() => {}) }}>
          <p className="muted small">Available to move: {taka(state.spendable)}</p>
          <input type="number" min="1" max={state.spendable} placeholder="Amount ৳" value={amt} onChange={(e) => setAmt(e.target.value)} required autoFocus />
          <button className="btn primary block">Move to goal</button>
        </form>
      </Modal>}
    </div>
  )
}
