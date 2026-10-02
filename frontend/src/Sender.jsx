import { useEffect, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { Progress } from './ui'

export default function Sender({ hid, role, user, act, tick, person }) {
  const [data, setData] = useState(null)
  const [intent, setIntent] = useState({ in_days: 14, amount: 25000 })
  const [note, setNote] = useState('')
  const H = { role, user }
  const sid = `S-${hid}`

  useEffect(() => { api(`/sender/${sid}/goals`, H).then(setData).catch((e) => setData({ error: e.message })) /* eslint-disable-next-line */ }, [hid, tick])
  if (!data) return <p className="muted">Loading…</p>
  if (data.error) return <p className="error">{data.error}</p>
  const c = data.consent
  const b = data.bills

  return (
    <div className="phone">
      <div className="phone-body">
        <div className="stackv">
          <section className="card">
            <h2>Hello {person?.sender_name} 👋</h2>
            <p className="muted small">You send money home from {person?.sender_city} to {person?.name}'s family. You only see what the family chooses to share. This protects trust and prevents monitoring of family spending.</p>
            {!c.sender_accepted
              ? <button className="primary" onClick={() => act(() => api(`/sender/${sid}/accept`, { ...H, method: 'POST' }))}>Accept the family link</button>
              : <p className="small">Link accepted ✓</p>}
          </section>

          {b && (
            <section className={`card ${b.status === 'all_covered' ? '' : 'flag'}`}>
              <h2>Bills and EMIs this month</h2>
              <p className="big">{b.status === 'all_covered' ? '✅ All covered' : `⚠️ ${b.at_risk_count} payment${b.at_risk_count > 1 ? 's' : ''} at risk`}</p>
              {b.send_by
                ? <p>Suggested next transfer: sending by <b>{fmtDate(b.send_by)}</b> would cover all bills on time.</p>
                : <p className="muted small">Nothing needs an earlier transfer right now.</p>}
              {b.family_asked && <p className="small">💬 The family asked if an earlier transfer is possible. It is your decision.</p>}
            </section>
          )}

          <section className="card">
            <h2>Shared goals</h2>
            {data.goals.length === 0 && <p className="muted small">{data.message || 'No goals shared yet.'}</p>}
            {data.goals.map((g) => (
              <div key={g.name} className="goal">
                <div className="row between"><b>{g.name}</b><span className="small">{g.pct}% {g.on_track ? '· on track' : '· needs attention'}</span></div>
                <Progress pct={g.pct} />
              </div>
            ))}
            {data.savings_total != null && <p className="small">Family savings (shared with you): <b>{taka(data.savings_total)}</b></p>}
            <p className="small muted">Progress only. You cannot see individual transactions.</p>
          </section>

          <section className="card">
            <h2>📅 Planning a transfer?</h2>
            <p className="muted small">Telling the family helps their forecast. Optional.</p>
            <div className="row wrap">
              <input type="number" value={intent.in_days} min="1" max="90" style={{ width: 80 }} onChange={(e) => setIntent({ ...intent, in_days: +e.target.value })} />
              <span className="small">days</span>
              <input type="number" value={intent.amount} min="1" style={{ width: 110 }} onChange={(e) => setIntent({ ...intent, amount: +e.target.value })} />
              <button disabled={!c.sender_accepted} onClick={() => act(async () => { const r = await api(`/sender/${sid}/intent`, { ...H, method: 'POST', body: intent }); setNote(r.note) })}>Share plan</button>
            </div>
            {note && <p className="small">{note}</p>}
          </section>

          <section className="card">
            <h2>🔒 What the family shares</h2>
            {[['goal_progress', 'Goal progress'], ['savings_total', 'Total savings'], ['bills_status', 'Bills & EMI status']].map(([k, label]) => (
              <div className="row between" key={k} style={{ margin: '6px 0' }}>
                <span>{label}</span>
                <span className="small">{c.scopes[k] === 'granted' ? '✓ shared' : c.scopes[k] === 'requested' ? 'requested…' : 'not shared'}
                  {c.scopes[k] !== 'granted' && c.scopes[k] !== 'requested' && <button className="link" onClick={() => act(() => api(`/sender/${sid}/request`, { ...H, method: 'POST', body: { scope: k } }))}>Ask the family</button>}</span>
              </div>
            ))}
            <p className="small muted">The family can accept or decline any request.</p>
          </section>
        </div>
      </div>
    </div>
  )
}
