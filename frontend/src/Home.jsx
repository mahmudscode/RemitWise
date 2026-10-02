import { useEffect, useState } from 'react'
import { api, fmtDate, longDate, taka } from './api'
import { AI, Avatar, Bar, Chip, FEATURE, Modal, Projection } from './ui'

export const subLine = (b) => {
  if (b.display_status === 'paid') return `Paid ${b.paid_date ? fmtDate(b.paid_date) : ''}`
  if (!b.autopay) return `Due ${fmtDate(b.due_date)} · paused`
  if (b.display_status === 'at_risk') return `Due ${fmtDate(b.due_date)} · not fully covered`
  if (b.variable && b.amount == null) return `Estimate · higher in summer · due ${fmtDate(b.due_date)}`
  return `Due ${fmtDate(b.due_date)} · pays on due date`
}

export default function Home({ hid, state, tick, lang, H, go, person }) {
  const [home, setHome] = useState(null)
  const [fc, setFc] = useState(null)
  const [pj, setPj] = useState(null)
  const [sum, setSum] = useState(null)
  const [facts, setFacts] = useState(false)

  useEffect(() => {
    api(`/households/${hid}/home`, H).then(setHome).catch(() => setHome(null))
    api(`/households/${hid}/forecast`, H).then(setFc).catch(() => setFc(null))
    api(`/households/${hid}/plan/projection`, H).then(setPj).catch(() => setPj(null))
    api(`/households/${hid}/summary?type=monthly&lang=${lang}`, H).then(setSum).catch(() => setSum(null))
    // eslint-disable-next-line
  }, [hid, tick, lang])

  const f = fc?.forecast
  const conf = f ? { high: 'high', medium: 'medium', low: 'low' }[fc.confidence_label] : ''
  const confPct = f ? Math.max(10, Math.min(100, Math.round(100 - ((f.rem_p90 - f.rem_p10) / 40) * 100))) : 0
  const safe = home?.safe

  return (
    <div className="stackv">
      <div className="pagehead">
        <div>
          <p className="eyebrow only-mobile">Family wallet</p>
          <h1>Good morning, {person?.name}</h1>
          <p className="only-desktop">{longDate(state.date)} · Family wallet</p>
        </div>
        <div className="row"><button className="btn primary only-desktop" onClick={() => go('payments', { add: true })}>+ Add payment</button><Avatar text={person?.name} /></div>
      </div>

      <div className="grid3">
        <section className="card blue">
          <p className="bal-label">Available balance</p>
          <p className="bal-big">{taka(home?.available ?? state.spendable)}</p>
          <span className="pill-dark">{taka(home?.reserved_bills ?? state.vault)} reserved for bills &amp; EMI</span>
        </section>

        <section className="card">
          <div className="row between"><span className="muted">Next remittance</span><AI why={<WhyForecast fc={fc} />} /></div>
          {f ? (<>
            <p className="big">Expected in {Math.round(f.rem_p10)}–{Math.round(f.rem_p90)} days</p>
            <p className="muted small">About {taka(f.amt_p10)} – {taka(f.amt_p90)} from {person?.sender_name} ({person?.sender_city})</p>
            <Bar pct={confPct} />
            <div className="row between small muted"><span>Confidence: {conf}{f.overdue ? ' · overdue, range widened' : ''}</span><WhyLink fc={fc} /></div>
          </>) : <p className="muted" style={{ marginTop: 8 }}>Collecting more history…</p>}
        </section>

        <section className="card">
          <div className="row between"><span className="muted">Safe to spend</span><AI label="Estimate" title="How this is worked out" why={<WhySafe s={safe} />} /></div>
          {safe ? (<>
            <p className="big txt-green" style={safe.status === 'amber' ? { color: 'var(--amber)' } : safe.status === 'red' ? { color: 'var(--red)' } : null}>{taka(safe.per_day)} <small>/ day</small></p>
            <Bar tone={safe.status === 'green' ? 'green' : safe.status} pct={(safe.per_day / Math.max(safe.usual_per_day, 1)) * 100} />
            <p className="small muted">Until your next expected transfer (about {safe.days} days), without missing any bill. You usually spend about {taka(safe.usual_per_day)} a day.</p>
          </>) : <p className="muted" style={{ marginTop: 8 }}>Available once a forecast exists.</p>}
        </section>
      </div>

      {home?.alert && (
        <div className={`banner ${home.alert.severity === 'red' ? 'red' : ''}`}>
          <span>Heads up: you may run short about {home.alert.days_short} day{home.alert.days_short === 1 ? '' : 's'} before your next transfer.</span>
          <button className="link" onClick={() => go('plan')}>See options →</button>
        </div>
      )}

      <div className="grid2">
        <section className="card only-desktop">
          <div className="row between"><h2>Projected balance until next transfer</h2><AI label="AI forecast" /></div>
          <Projection pj={pj} height={210} />
        </section>
        <section className="card">
          <div className="row between" style={{ marginBottom: 10 }}><h2>Upcoming payments</h2><button className="link" onClick={() => go('payments')}>See all</button></div>
          {(home?.upcoming || []).length === 0 && <p className="muted small">Nothing due soon.</p>}
          {(home?.upcoming || []).map((b) => (
            <div className="item" key={b.key} style={{ cursor: 'default' }} onClick={() => go('payments')}>
              <Avatar text={b.name} />
              <div className="grow"><b>{b.name}</b><small>{subLine(b)}</small></div>
              <div className="right"><b>{taka(b.amount ?? b.expected)}</b><Chip status={b.display_status} /></div>
            </div>
          ))}
        </section>
      </div>

      <div className="grid2" style={{ gridTemplateColumns: '1.35fr 1fr' }}>
        <section className="card purple">
          <span className="ai" style={{ background: 'transparent', padding: 0 }}>AI summary</span>
          {sum ? (<>
            <p style={{ margin: '8px 0', fontSize: 15 }}>{sum.text}</p>
            <span className="tag">{sum.label} · {sum.source}</span> <button className="link" onClick={() => setFacts(!facts)}>{facts ? 'Hide' : 'Show'} the facts used</button>
            {facts && <pre>{JSON.stringify(sum.source_facts, null, 1)}</pre>}
          </>) : <p className="muted">–</p>}
        </section>
        <section className="card">
          <div className="row between" style={{ marginBottom: 6 }}><h2>Goals</h2><button className="link" onClick={() => go('goals')}>View all</button></div>
          {state.goals.length === 0 && <p className="muted small">No goals yet.</p>}
          {state.goals.slice(0, 3).map((g) => (
            <div key={g.id} style={{ margin: '10px 0' }}>
              <div className="row between"><span>{g.name}</span><b className="txt-blue">{Math.round(g.pct)}%</b></div>
              <Bar pct={g.pct} />
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}

function WhyLink({ fc }) {
  const [open, setOpen] = useState(false)
  return <><button className="link" onClick={() => setOpen(true)}>Why?</button>{open && <Modal title="Why this estimate?" onClose={() => setOpen(false)}><WhyForecast fc={fc} /></Modal>}</>
}

export const WhyForecast = ({ fc }) => (
  <div>
    <p>This is a forecast made when your last transfer arrived. It looks at how often and how much your sender usually sends, the time of year, and recent delays.</p>
    {fc?.drivers?.length > 0 && <ul className="why">{fc.drivers.map((d, i) => <li key={i}>{FEATURE[d.feature] || d.feature.replace(/_/g, ' ')}: {d.effect_days > 0 ? 'adds' : 'saves'} about {Math.abs(d.effect_days).toFixed(1)} days</li>)}</ul>}
    {fc?.forecast?.naive && <p className="small muted">A simple “same as last time” guess would say {fc.forecast.naive.gap} days and {taka(fc.forecast.naive.amt)}.</p>}
    <p className="small muted">If the transfer is late, the range is widened instead of pretending the forecast still holds.</p>
  </div>
)
const WhySafe = ({ s }) => (
  <div>
    <p>We take the money you can spend, subtract bills that are not yet covered ({taka(s?.bills_not_yet_covered)}), and divide by the days until your next transfer is likely to arrive, leaning toward the later end so a late transfer does not catch you out.</p>
    <p className="small muted">It is a guide, not a limit. You decide what to spend.</p>
  </div>
)
