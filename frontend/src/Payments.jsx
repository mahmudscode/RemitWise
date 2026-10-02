import { useEffect, useMemo, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { AI, Chip, KIND_ICON, Modal } from './ui'

const COLOR = { paid: 'green', scheduled: 'blue', at_risk: 'amber', needs_review: 'amber', overdue: 'red' }

export default function Payments({ hid, tick, H, act }) {
  const [data, setData] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [why, setWhy] = useState(null)
  const [form, setForm] = useState({ biller: '', kind: 'utility', account_number: '', usual_amount: '', due_day: 10, monthly_limit: '', confirm_over_limit: true })
  const [err, setErr] = useState('')

  useEffect(() => { api(`/households/${hid}/bills`, H).then(setData).catch(() => setData(null)) /* eslint-disable-next-line */ }, [hid, tick])

  const month = useMemo(() => {
    if (!data) return null
    const t = new Date(data.today + 'T00:00:00')
    const first = new Date(t.getFullYear(), t.getMonth(), 1)
    const days = new Date(t.getFullYear(), t.getMonth() + 1, 0).getDate()
    const byDay = {}
    data.items.forEach((i) => { const d = new Date(i.due_date + 'T00:00:00'); if (d.getMonth() === t.getMonth() && d.getFullYear() === t.getFullYear()) (byDay[d.getDate()] ||= []).push(i) })
    return { first, days, byDay, label: t.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }), today: t.getDate() }
  }, [data])

  if (!data) return <p className="muted">Loading…</p>
  const flagged = data.items.filter((i) => i.display_status === 'needs_review')
  const upcoming = data.items.filter((i) => ['scheduled', 'at_risk'].includes(i.display_status))
  const recent = data.items.filter((i) => ['paid', 'overdue'].includes(i.display_status)).reverse()

  const resolve = (key, action) => act(() => api(`/households/${hid}/bills/resolve?key=${encodeURIComponent(key)}`, { ...H, method: 'POST', body: { action } })).catch(() => {})
  const toggle = (bid, on) => act(() => api(`/households/${hid}/bills/${bid}/autopay`, { ...H, method: 'POST', body: { on } }))
  const add = async (e) => {
    e.preventDefault(); setErr('')
    try {
      await act(() => api(`/households/${hid}/bills/mandates`, { ...H, method: 'POST', body: { ...form, usual_amount: +form.usual_amount, due_day: +form.due_day, monthly_limit: +form.monthly_limit } }))
      setShowAdd(false); setForm({ ...form, biller: '', account_number: '', usual_amount: '', monthly_limit: '' })
    } catch (ex) { setErr(ex.message) }
  }

  return (
    <div className="stackv">
      <section className="card">
        <h2>{month.label}</h2>
        <div className="cal">
          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => <b key={i} className="calh">{d}</b>)}
          {Array.from({ length: month.first.getDay() }).map((_, i) => <span key={'p' + i} />)}
          {Array.from({ length: month.days }).map((_, i) => {
            const d = i + 1, items = month.byDay[d] || []
            return <div key={d} className={`calc ${d === month.today ? 'today' : ''}`}><span>{d}</span>
              <div className="dots">{items.slice(0, 4).map((x) => <i key={x.key} className={`dot ${COLOR[x.display_status]}`} title={`${x.name}: ${x.display_status}`} />)}</div></div>
          })}
        </div>
        <p className="small muted"><i className="dot green" /> paid <i className="dot blue" /> scheduled <i className="dot amber" /> needs attention <i className="dot red" /> overdue</p>
      </section>

      {flagged.map((b) => (
        <section className="card flag" key={b.key}>
          <h2>⚠️ {b.name} bill needs your review</h2>
          <p>{b.name} bill <b>{taka(b.amount)}</b> {b.note ? `is ${b.note.split(' (')[0]}` : 'is unusual'}. Approve, dispute, or pay manually?</p>
          <div className="row wrap">
            <button className="primary" onClick={() => resolve(b.key, 'approve')}>Approve</button>
            <button onClick={() => resolve(b.key, 'dispute')}>Dispute</button>
            <button className="ghost" onClick={() => resolve(b.key, 'pay_manually')}>Pay manually</button>
            <button className="link" onClick={() => setWhy(b)}>Why?</button>
          </div>
          <p className="small muted">It was not paid automatically because it is much higher than usual. The decision is yours.</p>
        </section>
      ))}

      <section className="card">
        <div className="row between"><h2>Auto-pay</h2><button className="ghost" onClick={() => setShowAdd(!showAdd)}>{showAdd ? 'Close' : '+ Add new'}</button></div>
        <p className="small muted">Bill vault: {taka(data.vault)} set aside · late fees so far {taka(data.late_fees)}</p>
        {showAdd && (
          <form className="form" onSubmit={add}>
            <input placeholder="Biller (e.g. Water supply, Bike EMI)" value={form.biller} onChange={(e) => setForm({ ...form, biller: e.target.value })} required />
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}><option value="utility">Utility</option><option value="emi">EMI / loan</option><option value="school">School</option><option value="other">Other</option></select>
            <input placeholder="Account / customer number" value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} required minLength={4} />
            <div className="row"><input type="number" placeholder="Usual ৳" value={form.usual_amount} onChange={(e) => setForm({ ...form, usual_amount: e.target.value })} required min="1" />
              <input type="number" placeholder="Due day (1-28)" value={form.due_day} onChange={(e) => setForm({ ...form, due_day: e.target.value })} min="1" max="28" required /></div>
            <input type="number" placeholder="Monthly limit ৳" value={form.monthly_limit} onChange={(e) => setForm({ ...form, monthly_limit: e.target.value })} required min="1" />
            <label className="toggle"><input type="checkbox" checked={form.confirm_over_limit} onChange={(e) => setForm({ ...form, confirm_over_limit: e.target.checked })} /><span>Ask me to confirm payments over the limit</span></label>
            {err && <p className="small" style={{ color: 'var(--red)' }}>{err}</p>}
            <button className="primary">Set up auto-pay</button>
            <p className="small muted">Demo only: no real account or money is connected.</p>
          </form>
        )}
        {[['Upcoming', upcoming], ['Recent', recent]].map(([label, list]) => list.length > 0 && (
          <div key={label}><h3 className="sub">{label}</h3>
            {list.map((b) => <BillCard key={b.key} b={b} toggle={toggle} />)}</div>
        ))}
        {data.mandates.length > 0 && <details><summary>Manage mandates</summary>
          {data.mandates.map((m) => (
            <div className="strip" key={m.bill_id}><span className="ico">{KIND_ICON[m.kind]}</span>
              <div className="grow"><b>{m.name}</b><small>usual {taka(m.usual)} · due day {m.due_dom} · limit {taka(m.monthly_limit)}</small></div>
              <button className="link" onClick={() => act(() => api(`/households/${hid}/bills/mandates/${m.bill_id}`, { ...H, method: 'DELETE' }))}>Cancel</button></div>
          ))}</details>}
      </section>

      {why && <Modal title={`Why was the ${why.name} bill flagged?`} onClose={() => setWhy(null)}>
        <p>Billed: <b>{taka(why.amount)}</b>. Usual estimate: <b>{taka(why.expected)}</b> (same month last year). That is <b>{(why.amount / why.expected).toFixed(1)}x</b> higher; we hold anything above {1.8}x for your review.</p>
        <p className="small muted">If you dispute it, we assume it is corrected to the estimate before payment (a demo assumption).</p>
      </Modal>}
    </div>
  )
}

function BillCard({ b, toggle }) {
  const est = b.variable && b.amount == null
  return (
    <div className="bill">
      <div className="row between">
        <div className="row"><span className="ico">{KIND_ICON[b.kind] || '🧾'}</span><b>{b.name}</b></div>
        <Chip status={b.display_status} />
      </div>
      <div className="row between small">
        <span>{est ? <>about <b>{taka(b.expected)}</b> <AI label="Estimate" title="How we estimate" why={<p>Based on what this bill was in the same month last year, adjusted if it was unusual. On our synthetic data this is about 10% off on average, versus about 16% for “same as last month”.</p>} /></> : <b>{taka(b.amount ?? b.expected)}</b>}</span>
        <span className="muted">Due {fmtDate(b.due_date)}</span>
      </div>
      <div className="row between small">
        <span className="muted">{b.display_status === 'paid' ? `Paid${b.paid_via ? ` from ${b.paid_via}` : ''}` : b.autopay ? `Will pay on ${fmtDate(b.planned_date)}` : 'You pay this one yourself'}</span>
        <label className="switch"><input type="checkbox" checked={b.autopay} onChange={(e) => toggle(b.bill_id, e.target.checked)} /><span>Auto-pay</span></label>
      </div>
      {b.note && <p className="small muted">{b.note}</p>}
    </div>
  )
}
