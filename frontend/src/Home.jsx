import { useEffect, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { AI, Chip, KIND_ICON } from './ui'

export default function Home({ hid, state, tick, lang, H, onNav }) {
  const [home, setHome] = useState(null)
  const [fc, setFc] = useState(null)
  const [sum, setSum] = useState(null)
  const [facts, setFacts] = useState(false)

  useEffect(() => {
    api(`/households/${hid}/home`, H).then(setHome).catch(() => setHome(null))
    api(`/households/${hid}/forecast`, H).then(setFc).catch(() => setFc(null))
    api(`/households/${hid}/summary?type=monthly&lang=${lang}`, H).then(setSum).catch(() => setSum(null))
    // eslint-disable-next-line
  }, [hid, tick, lang])

  const f = fc?.forecast
  const width = f ? f.rem_p90 - f.rem_p10 : 0
  const conf = f ? Math.max(8, Math.min(100, Math.round(100 - (width / 40) * 100))) : 0

  return (
    <div className="stackv">
      <section className="card balance">
        <small>Available balance</small>
        <div className="huge">{taka(home?.available ?? state.spendable)}</div>
        <p className="muted small">{taka(home?.reserved_bills ?? state.vault)} reserved for bills and EMI · {taka(home?.savings ?? 0)} saved</p>
      </section>

      {home?.alert && (
        <section className={`banner ${home.alert.severity}`}>
          <span>⚠️ {home.alert.text}</span>
          <button className="link" onClick={() => onNav('plan')}>See options</button>
        </section>
      )}

      <section className="card">
        <div className="row between"><h2>Next remittance</h2>{f && <AI why={<WhyForecast fc={fc} />} />}</div>
        {f ? (<>
          <p className="big">{fmtDate(f.next_date_p10)} – {fmtDate(f.next_date_p90)}</p>
          <p className="muted small">Expected in {Math.round(f.rem_p10)} to {Math.round(f.rem_p90)} days · about {taka(f.amt_p10)} – {taka(f.amt_p90)}{f.overdue && ' · overdue, range widened'}</p>
          <div className="conf"><div style={{ width: `${conf}%` }} /></div>
          <p className="small muted">Confidence: {fc.confidence_label}. A range, not a promise.</p>
        </>) : <p className="muted">Collecting more history…</p>}
      </section>

      <section className="card">
        <div className="row between"><h2>Safe to spend</h2>{home?.safe && <AI label="Estimate" title="How this is worked out" why={<WhySafe s={home.safe} />} />}</div>
        {home?.safe ? (<>
          <p className="big"><span className={`dot ${home.safe.status}`} /> {taka(home.safe.per_day)} <small>per day</small></p>
          <div className={`meter ${home.safe.status}`}><div style={{ width: `${Math.min(100, (home.safe.per_day / Math.max(home.safe.usual_per_day, 1)) * 100)}%` }} /></div>
          <p className="small muted">Until your next transfer (about {home.safe.days} days) without missing bills. You usually spend about {taka(home.safe.usual_per_day)} a day.</p>
        </>) : <p className="muted">Available once a forecast exists.</p>}
      </section>

      <section className="card">
        <div className="row between"><h2>Upcoming payments</h2><button className="link" onClick={() => onNav('payments')}>All</button></div>
        {(home?.upcoming || []).length === 0 && <p className="muted small">Nothing due soon.</p>}
        {(home?.upcoming || []).map((b) => (
          <div className="strip" key={b.key}>
            <span className="ico">{KIND_ICON[b.kind] || '🧾'}</span>
            <div className="grow"><b>{b.name}</b><small>{fmtDate(b.due_date)} · {b.amount != null ? taka(b.amount) : `about ${taka(b.expected)}`}</small></div>
            <Chip status={b.display_status} />
            <span title={b.display_status === 'at_risk' ? 'Not covered yet' : 'Covered'}>{b.display_status === 'at_risk' ? '⚠️' : '✓'}</span>
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Your month in plain words</h2>
        {sum ? (<>
          <p className="said">{sum.text}</p>
          <small className="tag">{sum.label} · {sum.source}</small>{' '}
          <button className="link" onClick={() => setFacts(!facts)}>{facts ? 'Hide' : 'Show'} the facts used</button>
          {facts && <pre>{JSON.stringify(sum.source_facts, null, 1)}</pre>}
        </>) : <p className="muted">–</p>}
      </section>
    </div>
  )
}

const WhyForecast = ({ fc }) => (
  <div>
    <p>This is a forecast made when your last transfer arrived. It looks at how often and how much your sender usually sends, the time of year, and recent delays.</p>
    {fc?.drivers?.length > 0 && <ul className="why">{fc.drivers.map((d, i) => <li key={i}>{d.feature.replace(/_/g, ' ')} = {Math.round(d.value * 10) / 10} → {d.effect_days > 0 ? '+' : ''}{d.effect_days.toFixed(1)} days</li>)}</ul>}
    {fc?.forecast?.naive && <p className="small muted">A simple “same as last time” guess would say {fc.forecast.naive.gap} days and {taka(fc.forecast.naive.amt)}.</p>}
    <p className="small muted">If the transfer is late, the range is widened instead of pretending the forecast still holds.</p>
  </div>
)
const WhySafe = ({ s }) => (
  <div>
    <p>We take the money you can spend, subtract bills that are not yet covered ({taka(s.bills_not_yet_covered)}), and divide by the days until your next transfer is likely to arrive (leaning toward the later end, so a late transfer does not catch you out).</p>
    <p className="small muted">It is a guide, not a limit. You decide what to spend.</p>
  </div>
)
