import { useEffect, useRef, useState } from 'react'
import { api, taka } from './api'
import { AI, Progress } from './ui'

export default function Goals({ hid, state, H, act, tick }) {
  const [consent, setConsent] = useState(null)
  const [form, setForm] = useState({ name: '', target: '', days: 240 })
  const [sug, setSug] = useState(null)
  const [msg, setMsg] = useState('')
  const timer = useRef(null)

  useEffect(() => { api(`/households/${hid}/consent`, H).then(setConsent).catch(() => {}) /* eslint-disable-next-line */ }, [hid, tick])

  useEffect(() => {
    clearTimeout(timer.current)
    if (!form.target || +form.target <= 0) { setSug(null); return }
    timer.current = setTimeout(() => api(`/households/${hid}/goals/suggest`, { ...H, method: 'POST', body: { target: +form.target, days: +form.days } }).then(setSug).catch(() => setSug(null)), 300)
    // eslint-disable-next-line
  }, [form.target, form.days, hid])

  const add = async (e) => {
    e.preventDefault(); setMsg('')
    await act(async () => {
      const r = await api(`/households/${hid}/goals`, { ...H, method: 'POST', body: { name: form.name, target: +form.target, days: +form.days, priority: 2 } })
      setMsg(r.feasible ? `Needs about ${taka(r.per_transfer_needed)} per transfer.` : r.note)
      setForm({ name: '', target: '', days: 240 }); setSug(null)
    })
  }

  return (
    <div className="stackv">
      {state.goals.map((g) => (
        <section className="card" key={g.id}>
          <div className="row between"><h2>{g.name}</h2><span className="small muted">{Math.round(g.days_left)} days left</span></div>
          <div className="row between"><b>{taka(g.current)}</b><span className="muted">of {taka(g.target)}</span></div>
          <Progress pct={g.pct} />
          <div className="row between small" style={{ marginTop: 8 }}>
            <span>{g.pace.text} <AI label="Estimate" title="How this is estimated" why={<p>This uses your last few contributions to this goal and how often transfers usually arrive. It is an estimate, and changes as your transfers change.</p>} /></span>
          </div>
          <div className="row between" style={{ marginTop: 8 }}>
            <label className="switch"><input type="checkbox" checked={g.shared} onChange={(e) => act(() => api(`/households/${hid}/goals/${g.id}/share`, { ...H, method: 'POST', body: { shared: e.target.checked } }))} /><span>Share progress with sender</span></label>
            <button className="link" onClick={() => act(() => api(`/households/${hid}/goals/${g.id}`, { ...H, method: 'DELETE' }))}>Remove</button>
          </div>
        </section>
      ))}
      <section className="card">
        <h2>New goal</h2>
        <form className="form" onSubmit={add}>
          <input placeholder="Goal name (e.g. Education)" maxLength={40} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <div className="row"><input type="number" placeholder="Target ৳" min="1" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} required />
            <input type="number" title="Days to deadline" min="14" value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} /></div>
          {sug && (
            <div className={`suggest ${sug.realistic ? 'ok' : 'warn'}`}>
              <b>Suggested: {taka(sug.suggested_monthly)} a month</b> <AI why={<p>{sug.explanation} Your goal needs about {taka(sug.needed_monthly)} a month for this deadline.</p>} />
              <small>{sug.months_at_suggested ? `About ${sug.months_at_suggested} months at that pace.` : 'No spare money is expected right now.'} {sug.realistic ? '' : 'This deadline looks tight; consider a longer one.'}</small>
            </div>
          )}
          <button className="primary">Create goal</button>
        </form>
        {msg && <p className="small muted">{msg}</p>}
      </section>

      <section className="card">
        <h2>🤝 Sharing with your sender</h2>
        <p className="small muted">Your sender sees goal progress only, never your transactions, unless you choose to share more. You can change this any time, and you can say no to any request.</p>
        {consent && (<>
          <p className="small">Sender link: {consent.sender_accepted ? 'accepted ✓' : 'waiting for the sender to accept'}</p>
          {[['goal_progress', 'Goal progress (the goals you switched on above)'], ['savings_total', 'Total savings'], ['bills_status', 'Bills and EMI status, and a suggested send-by date']].map(([k, label]) => (
            <label key={k} className="toggle">
              <input type="checkbox" checked={consent.scopes[k] === 'granted'} onChange={(e) => act(() => api(`/households/${hid}/consent`, { ...H, method: 'POST', body: { scope: k, state: e.target.checked ? 'granted' : 'revoked' } }))} />
              <span>{label}{consent.scopes[k] === 'requested' && <em> · your sender asked to see this</em>}</span>
            </label>
          ))}
          <p className="small muted">Spending details are not shared in this demo.</p>
        </>)}
      </section>
    </div>
  )
}
