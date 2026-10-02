import { useEffect, useState } from 'react'
import { api, pct, taka } from './api'
import { AI } from './ui'

export default function Insights({ hid, tick, lang, H }) {
  const [d, setD] = useState(null)
  const [sum, setSum] = useState(null)
  const [facts, setFacts] = useState(false)
  useEffect(() => {
    api(`/households/${hid}/insights`, H).then(setD).catch(() => setD(null))
    api(`/households/${hid}/summary?type=monthly&lang=${lang}`, H).then(setSum).catch(() => setSum(null))
    // eslint-disable-next-line
  }, [hid, tick, lang])
  if (!d) return <p className="muted">Loading…</p>
  const bars = (items, key = 'effect_days') => {
    const max = Math.max(...items.map((i) => Math.abs(i[key] ?? i.magnitude ?? 0)), 0.01)
    return items.map((i, k) => {
      const v = i[key] ?? i.magnitude ?? 0
      return <div className="barrow" key={k}><span>{(i.feature || i.factor || '').replace(/_/g, ' ')}</span>
        <div className="bartrack"><div className={v < 0 ? 'neg' : 'pos'} style={{ width: `${(Math.abs(v) / max) * 100}%` }} /></div>
        <b>{key === 'effect_days' ? `${v > 0 ? '+' : ''}${v.toFixed(1)}d` : `${Math.round(v * 100)}%`}</b></div>
    })
  }
  return (
    <div className="stackv">
      <section className="card">
        <h2>Your month</h2>
        {sum ? (<>
          <p className="said">{sum.text}</p>
          <small className="tag">{sum.label} · {sum.source}</small>{' '}
          <button className="link" onClick={() => setFacts(!facts)}>{facts ? 'Hide' : 'Show'} the facts used</button>
          {facts && <pre>{JSON.stringify(sum.source_facts, null, 1)}</pre>}
        </>) : <p className="muted">–</p>}
      </section>
      <section className="grid2">
        <Tile label="Late fees avoided" value={taka(d.late_fees_avoided)} />
        <Tile label="On-time payments" value={d.on_time_rate == null ? '–' : pct(d.on_time_rate)} sub={`${d.bills_due} bills`} />
        <Tile label="Savings built" value={taka(d.savings_built)} />
        <Tile label="Unusual bills caught" value={d.anomalies_caught} sub={`${taka(d.overbilling_avoided)} saved`} />
      </section>
      <section className="card">
        <div className="row between"><h2>Why the forecast looks like this</h2><AI why={<p>Each bar is how much one factor moved the predicted gap before your next transfer, from the model's feature contributions. Positive means later.</p>} /></div>
        {d.forecast_drivers.length ? bars(d.forecast_drivers) : <p className="muted">–</p>}
      </section>
      <section className="card">
        <div className="row between"><h2>Why a warning appears</h2><AI label="Rule trace" why={<p>These are the reasons the early-warning check found, such as spending above usual or a late transfer. Bigger bar means bigger effect.</p>} /></div>
        {d.warning_drivers.length ? bars(d.warning_drivers, 'magnitude') : <p className="muted small">No warning reasons right now.</p>}
      </section>
    </div>
  )
}
const Tile = ({ label, value, sub }) => <div className="card tile"><small>{label}</small><b>{value}</b>{sub && <small>{sub}</small>}</div>
