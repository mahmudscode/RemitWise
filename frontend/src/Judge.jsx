import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, pct, taka } from './api'

const A = { role: 'admin', user: '' }
const f1 = (x) => (x == null ? '–' : (Math.round(x * 10) / 10).toFixed(1))

export default function Judge({ hid, state, act, tick, person }) {
  const [ev, setEv] = useState(null)
  const [comp, setComp] = useState(0.8)
  const [per, setPer] = useState([])
  const [audit, setAudit] = useState([])
  const [card, setCard] = useState('')
  const [showCard, setShowCard] = useState(false)
  const [log, setLog] = useState('')

  useEffect(() => { api('/evaluation', A).then(setEv).catch((e) => setLog(e.message)); api('/data-card', A).then((r) => setCard(r.markdown)) }, [])
  useEffect(() => { api(`/compare?household_id=${hid}&compliance=${comp}`, A).then(setPer).catch(() => setPer([])) }, [hid, comp])
  useEffect(() => { api('/audit?limit=12', A).then(setAudit).catch(() => {}) }, [tick])

  const scen = (kind, value) => act(() => api(`/households/${hid}/scenario`, { ...A, method: 'POST', body: { kind, value } }))
  if (!ev) return <p className="muted">{log || 'Loading evaluation… run `python -m app.pipeline` if this stays empty.'}</p>

  const sum = ev.compare.summary
  const row = (policy, c) => sum.find((r) => r.policy === policy && (policy === 'baseline' || r.compliance === c))
  const base = row('baseline'), fx = row('fixed_rule', comp), rw = row('remitwise', comp)
  const o = ev.forecast.overall
  const metrics = [
    ['Shortfall days / year', 'shortfall_days_per_year', f1, true],
    ['Savings rate', 'savings_rate', pct, false],
    ['Emergency buffer (months)', 'emergency_months', f1, false],
    ['Kept in wallet after 24h', 'retained_share', pct, false],
  ]
  const chart = metrics.map(([label, k]) => ({ name: label, Without: base[k], 'Fixed 50/30/20': fx[k], RemitWise: rw[k] }))
  const mine = (p) => per.find((r) => r.policy === p)

  return (
    <div className="grid">
      <section className="card span2">
        <h2>🎛 Demo controls — {person?.name}</h2>
        <div className="row wrap">
          <button onClick={() => scen('delay', 14)}>Delay next transfer +14 days</button>
          <button onClick={() => scen('expense', Math.round(state.monthly_needs * 0.5))}>Large expense</button>
          <button onClick={() => scen('second_income', 5000)}>Add second income ৳5,000/mo</button>
          <button onClick={() => scen('family_member', 0.15)}>New family member (+15% needs)</button>
          <button className="danger" onClick={() => act(() => api(`/households/${hid}/reset`, { ...A, method: 'POST' }))}>Reset demo</button>
        </div>
        <p className="small muted">Scenario events change what happens in the replay; the forecaster does not know about them in advance.</p>
      </section>

      <section className="card span2">
        <div className="row between wrap">
          <h2>📊 A simulated year, with vs without RemitWise</h2>
          <label>Family follows the plan in <select value={comp} onChange={(e) => setComp(+e.target.value)}>{[0.6, 0.8, 1.0].map((c) => <option key={c} value={c}>{pct(c)}</option>)}</select> of cycles</label>
        </div>
        <p className="small muted"><b>Assumed, not measured:</b> how families behave with and without a plan. Simulated on {ev.compare.n_households} clean test households (never used for training). Results are shown across compliance levels so they can’t be cherry-picked.</p>
        <table>
          <thead><tr><th>Metric (avg over test households)</th><th>Without</th><th>Fixed 50/30/20</th><th>RemitWise</th></tr></thead>
          <tbody>{metrics.map(([label, k, fmt]) => <tr key={k}><td>{label}</td><td>{fmt(base[k])}</td><td>{fmt(fx[k])}</td><td><b>{fmt(rw[k])}</b></td></tr>)}</tbody>
        </table>
        <p className="small"><b>Honest reading:</b> both plans cut shortfalls sharply versus doing nothing. A fixed 50/30/20 rule performs about as well on shortfall days; RemitWise's clearer edge here is more money kept in the wallet and more saved, plus it adapts to uncertainty.</p>
        <div style={{ height: 220 }}>
          <ResponsiveContainer><BarChart data={chart.slice(0, 1)}><CartesianGrid strokeDasharray="3 3" stroke="var(--line)" /><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend />
            <Bar dataKey="Without" fill="#c2503a" /><Bar dataKey="Fixed 50/30/20" fill="#a0a7b4" /><Bar dataKey="RemitWise" fill="#1f7a5a" /></BarChart></ResponsiveContainer>
        </div>
        {mine('baseline') && mine('remitwise') && (
          <p className="small">For <b>{person?.name}</b> alone: {f1(mine('baseline').shortfall_days_per_year)} shortfall days/yr without → <b>{f1(mine('remitwise').shortfall_days_per_year)}</b> with RemitWise; kept in wallet {pct(mine('baseline').retained_share)} → <b>{pct(mine('remitwise').retained_share)}</b>.</p>
        )}
        <details><summary>By household type (regularity)</summary>
          <table><thead><tr><th>Type</th><th>Without</th><th>Fixed</th><th>RemitWise</th><th>(shortfall days / yr)</th></tr></thead><tbody>
            {['regular', 'semi', 'irregular'].map((c) => {
              const g = (p) => ev.compare.by_class.find((r) => r.cls === c && r.policy === p && (p === 'baseline' || r.compliance === comp))
              return <tr key={c}><td>{c}</td><td>{f1(g('baseline')?.shortfall_days_per_year)}</td><td>{f1(g('fixed_rule')?.shortfall_days_per_year)}</td><td>{f1(g('remitwise')?.shortfall_days_per_year)}</td><td /></tr>
            })}</tbody></table>
        </details>
      </section>

      <section className="card">
        <h2>🔮 Forecast quality <small>(clean test set)</small></h2>
        <table><thead><tr><th /><th>Model</th><th>“Same as last time”</th></tr></thead><tbody>
          <tr><td>Timing error (days)</td><td><b>{f1(o.gap_mae_model)}</b></td><td>{f1(o.gap_mae_naive)}</td></tr>
          <tr><td>Amount error (MAPE)</td><td><b>{pct(o.amt_mape_model)}</b></td><td>{pct(o.amt_mape_naive)}</td></tr>
          <tr><td>80% range coverage — timing</td><td colSpan="2">{pct(o.gap_coverage)}</td></tr>
          <tr><td>80% range coverage — amount</td><td colSpan="2">{pct(o.amt_coverage)}</td></tr>
        </tbody></table>
      </section>

      <section className="card">
        <h2>⚠️ Warning quality</h2>
        <table><thead><tr><th /><th>Monte-Carlo model</th><th>Simple threshold rule</th></tr></thead><tbody>
          <tr><td>Precision</td><td>{pct(ev.warning.model.precision)}</td><td><b>{pct(ev.warning.threshold_only_rule.precision)}</b></td></tr>
          <tr><td>Recall</td><td><b>{pct(ev.warning.model.recall)}</b></td><td>{pct(ev.warning.threshold_only_rule.recall)}</td></tr>
          <tr><td>Avg. warning lead (days)</td><td><b>{f1(ev.warning.model.mean_lead_days)}</b></td><td>{f1(ev.warning.threshold_only_rule.mean_lead_days)}</td></tr>
        </tbody></table>
        <p className="small muted">The model warns earlier and catches more shortages but raises more false alarms; the simple rule is more precise. Threshold {ev.warning.threshold} tuned on calibration households.</p>
      </section>

      <section className="card span2">
        <h2>⚖️ Fairness cuts <small>(forecast error, days — model vs naive)</small></h2>
        <table><thead><tr><th>Group</th><th>n</th><th>Timing MAE model</th><th>naive</th><th>Range coverage</th><th>Amount MAPE model</th><th>naive</th></tr></thead><tbody>
          {Object.entries(ev.forecast.by_group).flatMap(([grp, v]) => Object.entries(v).map(([k, b]) =>
            <tr key={grp + k}><td>{grp}: <b>{k}</b></td><td>{b.n}</td><td>{f1(b.gap_mae_model)}</td><td>{f1(b.gap_mae_naive)}</td><td>{pct(b.gap_coverage)}</td><td>{pct(b.amt_mape_model)}</td><td>{pct(b.amt_mape_naive)}</td></tr>))}
        </tbody></table>
        <p className="small muted">Irregular senders are forecast less accurately (as expected), but the model still beats the naive guess and the range stays honest about it. See the fairness plan in the docs.</p>
      </section>

      <section className="card">
        <h2>📜 Audit log</h2>
        <ul className="why small">{audit.map((a, i) => <li key={i}>{a.ts.slice(11, 19)} · {a.actor} · {a.action} {a.household_id || ''}</li>)}</ul>
      </section>

      <section className="card">
        <h2>🗂 Data card</h2>
        <button className="link" onClick={() => setShowCard(!showCard)}>{showCard ? 'Hide' : 'Show'} assumptions</button>
        {showCard && <pre>{card}</pre>}
      </section>
    </div>
  )
}
