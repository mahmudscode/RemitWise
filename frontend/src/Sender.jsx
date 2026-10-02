import { useEffect, useState } from 'react'
import { api, taka } from './api'

export default function Sender({ hid, state, role, user, act, tick, person }) {
  const [data, setData] = useState(null)
  const [intent, setIntent] = useState({ in_days: 14, amount: 25000 })
  const [note, setNote] = useState('')
  const H = { role, user }
  const sid = `S-${hid}`

  useEffect(() => { api(`/sender/${sid}/goals`, H).then(setData).catch((e) => setData({ error: e.message })) /* eslint-disable-next-line */ }, [hid, tick])

  if (!data) return <p className="muted">Loading…</p>
  if (data.error) return <p className="error">{data.error}</p>
  const c = data.consent

  return (
    <div className="grid">
      <section className="card span2">
        <h2>👋 Hello — you send money home to {person?.name}'s family</h2>
        <p className="muted">You only see what the family chooses to share. This protects trust and prevents monitoring of family spending.</p>
        {!c.sender_accepted
          ? <button className="primary" onClick={() => act(() => api(`/sender/${sid}/accept`, { ...H, method: 'POST' }))}>Accept the family link</button>
          : <p>Link accepted ✓</p>}
      </section>

      <section className="card span2">
        <h2>🎯 Shared goals</h2>
        {data.goals.length === 0 && <p className="muted">{data.message || 'No goals to show.'}</p>}
        {data.goals.map((g) => (
          <div key={g.name} className="goal">
            <div className="row between"><b>{g.name}</b><span>{g.pct}% {g.on_track ? '· on track' : '· needs attention'}</span></div>
            <div className="progress"><div style={{ width: `${g.pct}%` }} /></div>
          </div>
        ))}
        {data.savings_total != null && <p>Family savings total (shared with you): <b>{taka(data.savings_total)}</b></p>}
        <p className="small muted">Progress only. You cannot see individual transactions.</p>
      </section>

      <section className="card">
        <h2>📅 Planning a transfer?</h2>
        <p className="muted small">Telling the family helps their forecast. It is optional.</p>
        <div className="addgoal">
          <input type="number" value={intent.in_days} min="1" max="90" onChange={(e) => setIntent({ ...intent, in_days: +e.target.value })} />
          <input type="number" value={intent.amount} min="1" onChange={(e) => setIntent({ ...intent, amount: +e.target.value })} />
          <button className="ghost" disabled={!c.sender_accepted} onClick={() => act(async () => { const r = await api(`/sender/${sid}/intent`, { ...H, method: 'POST', body: intent }); setNote(r.note) })}>Share plan</button>
        </div>
        <p className="small muted">In {intent.in_days} days, about {taka(intent.amount)}.</p>
        {note && <p className="small">{note}</p>}
      </section>

      <section className="card">
        <h2>🔒 What the family shares</h2>
        {[['goal_progress', 'Goal progress'], ['savings_total', 'Total savings']].map(([k, label]) => (
          <div className="row between" key={k}>
            <span>{label}</span>
            <span>
              {c.scopes[k] === 'granted' ? '✓ shared' : c.scopes[k] === 'requested' ? 'requested…' : 'not shared'}
              {c.scopes[k] !== 'granted' && c.scopes[k] !== 'requested' && (
                <button className="link" onClick={() => act(() => api(`/sender/${sid}/request`, { ...H, method: 'POST', body: { scope: k } }))}>Ask the family</button>
              )}
            </span>
          </div>
        ))}
        <p className="small muted">The family can accept or decline any request.</p>
      </section>
    </div>
  )
}
