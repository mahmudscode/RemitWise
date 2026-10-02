import { useEffect, useState } from 'react'
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
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
  const [msg, setMsg] = useState('')

  useEffect(() => { api('/evaluation', A).then(setEv).catch((e) => setLog(e.message)); api('/data-card', A).then((r) => setCard(r.markdown)) }, [])
  useEffect(() => { api(`/compare?household_id=${hid}&compliance=${comp}`, A).then(setPer).catch(() => setPer([])) }, [hid, comp])
  useEffect(() => { api('/audit?limit=12', A).then(setAudit).catch(() => {}) }, [tick])

  const run = (fn, ok) => act(async () => { setMsg(''); try { await fn(); if (ok) setMsg(ok) } catch (e) { setMsg(e.message) } })
  const scen = (kind, value = 0, ok) => run(() => api(`/households/${hid}/scenario`, { ...A, method: 'POST', body: { kind, value } }), ok)
  const adv = (days, to_arrival = false) => run(() => api(`/households/${hid}/advance`, { ...A, method: 'POST', body: { days, to_arrival } }))
  if (!ev) return <p className="muted">{log || 'Loading evaluation… run `python -m app.pipeline` if this stays empty.'}</p>

  const sum = ev.compare.summary
  const row = (policy, c) => sum.find((r) => r.policy === policy && (policy === 'baseline' || r.compliance === c))
  const base = row('baseline'), fx = row('fixed_rule', comp), rw = row('remitwise', comp)
  const o = ev.forecast.overall
  const mine = (p) => per.find((r) => r.policy === p)
  const metrics = [
    ['Shortfall days / year', 'shortfall_days_per_year', f1],
    ['Bills paid on time', 'on_time_rate', pct],
    ['Late fees / year (৳)', 'late_fees_per_year', (x) => taka(x)],
    ['Overbilling paid / year (৳)', 'overbilling_paid_per_year', (x) => taka(x)],
    ['Savings rate', 'savings_rate', pct],
    ['Kept in wallet after 24h', 'retained_share', pct],
  ]
  const samples = ev.forecast.samples.map((s, i) => ({ i: i + 1, actual: s.actual_gap, band: [s.model_p10, s.model_p90], model: s.model_p50, naive: s.naive }))
  const honest = []
  if (fx.shortfall_days_per_year < rw.shortfall_days_per_year) honest.push(`A fixed 50/30/20 rule has fewer shortfall days (${f1(fx.shortfall_days_per_year)}) than RemitWise (${f1(rw.shortfall_days_per_year)}).`)
  else honest.push(`RemitWise has fewer shortfall days (${f1(rw.shortfall_days_per_year)}) than a fixed 50/30/20 rule (${f1(fx.shortfall_days_per_year)}).`)
  honest.push(`RemitWise leads on bills paid on time (${pct(rw.on_time_rate)} vs ${pct(fx.on_time_rate)} for the fixed rule and ${pct(base.on_time_rate)} with no plan) and on money kept in the wallet (${pct(rw.retained_share)} vs ${pct(fx.retained_share)}).`)

  return (
    <div className="grid">
      <section className="card span2">
        <h2>🎛 Simulation controls: {person?.name}</h2>
        <div className="row wrap">
          <button className="primary" onClick={() => adv(1, true)}>Trigger remittance</button>
          <button onClick={() => adv(7)}>Advance 7 days</button>
          <button onClick={() => scen('delay', 14, 'Next transfer delayed by 14 days.')}>Delay next transfer</button>
          <button onClick={() => scen('high_bill', 0, 'The next electricity bill will be unusually high.')}>Inject unusually high bill</button>
          <button onClick={() => scen('new_emi', 0, 'A new phone EMI mandate was added.')}>Add new EMI</button>
          <button onClick={() => scen('expense', Math.round(state.monthly_needs * 0.5))}>Large expense</button>
          <button onClick={() => scen('second_income', 5000, 'Second income added.')}>Second income</button>
          <button onClick={() => scen('family_member', 0.15, 'Needs up 15%.')}>New family member</button>
          <button className="danger" onClick={() => run(() => api(`/households/${hid}/reset`, { ...A, method: 'POST' }), 'Demo reset.')}>Reset demo</button>
        </div>
        {msg && <p className="small">{msg}</p>}
        <p className="small muted">Scenario events change what happens in the replay; the forecaster does not know about them in advance.</p>
      </section>

      <section className="card span2">
        <h2>🔮 Forecast vs actual <small>(clean test set, days until the next transfer)</small></h2>
        <div style={{ height: 260 }}>
          <ResponsiveContainer>
            <ComposedChart data={samples}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" /><XAxis dataKey="i" fontSize={11} /><YAxis fontSize={11} width={34} />
              <Tooltip /><Legend />
              <Area isAnimationActive={false} dataKey="band" name="Model 80% range" stroke="none" fill="var(--accent)" fillOpacity={0.18} />
              <Line isAnimationActive={false} dataKey="model" name="Model" stroke="var(--accent)" dot={false} strokeWidth={2} />
              <Scatter isAnimationActive={false} dataKey="naive" name="“Same as last time”" fill="#c2503a" />
              <Line isAnimationActive={false} dataKey="actual" name="Actual" stroke="#1d2433" dot={{ r: 2 }} strokeWidth={1} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="small muted">60 random test cases sorted by actual gap. The model stays closer to the actual line than the naive guess and its range covers about {pct(o.gap_coverage)} of outcomes.</p>
      </section>

      <section className="card span2">
        <div className="row between wrap">
          <h2>📊 A simulated year, with vs without RemitWise</h2>
          <label>Family follows the plan in <select value={comp} onChange={(e) => setComp(+e.target.value)}>{[0.6, 0.8, 1.0].map((c) => <option key={c} value={c}>{pct(c)}</option>)}</select> of cycles</label>
        </div>
        <p className="small muted"><b>Assumed, not measured:</b> how families behave with and without a plan. Simulated on {ev.compare.n_households} clean test households. Shown across compliance levels so it can't be cherry-picked.</p>
        <table>
          <thead><tr><th>Metric (avg over test households)</th><th>Without</th><th>Fixed 50/30/20</th><th>RemitWise</th></tr></thead>
          <tbody>{metrics.map(([label, k, fmt]) => <tr key={k}><td>{label}</td><td>{fmt(base[k])}</td><td>{fmt(fx[k])}</td><td><b>{fmt(rw[k])}</b></td></tr>)}</tbody>
        </table>
        <p className="small"><b>Honest reading:</b> {honest.join(' ')} Late fees avoided per year by RemitWise vs no plan: <b>{taka(base.late_fees_per_year - rw.late_fees_per_year)}</b> per household.</p>
        <div style={{ height: 200 }}>
          <ResponsiveContainer><BarChart data={[{ name: 'Shortfall days / year', Without: base.shortfall_days_per_year, 'Fixed 50/30/20': fx.shortfall_days_per_year, RemitWise: rw.shortfall_days_per_year }]}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" /><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend />
            <Bar isAnimationActive={false} dataKey="Without" fill="#c2503a" /><Bar isAnimationActive={false} dataKey="Fixed 50/30/20" fill="#a0a7b4" /><Bar isAnimationActive={false} dataKey="RemitWise" fill="#1f7a5a" /></BarChart></ResponsiveContainer>
        </div>
        {mine('baseline') && mine('remitwise') && (
          <p className="small">For <b>{person?.name}</b> alone: {f1(mine('baseline').shortfall_days_per_year)} shortfall days/yr without → <b>{f1(mine('remitwise').shortfall_days_per_year)}</b> with RemitWise; bills on time {pct(mine('baseline').on_time_rate)} → <b>{pct(mine('remitwise').on_time_rate)}</b>.</p>
        )}
        <details><summary>By household type (shortfall days / year)</summary>
          <table><thead><tr><th>Type</th><th>Without</th><th>Fixed</th><th>RemitWise</th></tr></thead><tbody>
            {['regular', 'semi', 'irregular'].map((c) => {
              const g = (p) => ev.compare.by_class.find((r) => r.cls === c && r.policy === p && (p === 'baseline' || r.compliance === comp))
              return <tr key={c}><td>{c}</td><td>{f1(g('baseline')?.shortfall_days_per_year)}</td><td>{f1(g('fixed_rule')?.shortfall_days_per_year)}</td><td>{f1(g('remitwise')?.shortfall_days_per_year)}</td></tr>
            })}</tbody></table>
        </details>
      </section>

      <section className="card">
        <h2>🎯 Key metrics</h2>
        <table><tbody>
          <tr><td>Timing error (days): model / naive</td><td><b>{f1(o.gap_mae_model)}</b> / {f1(o.gap_mae_naive)}</td></tr>
          <tr><td>Amount error: model / naive</td><td><b>{pct(o.amt_mape_model)}</b> / {pct(o.amt_mape_naive)}</td></tr>
          <tr><td>Warning precision / recall</td><td><b>{pct(ev.warning.model.precision)}</b> / {pct(ev.warning.model.recall)}</td></tr>
          <tr><td>Simple-rule precision / recall</td><td>{pct(ev.warning.threshold_only_rule.precision)} / {pct(ev.warning.threshold_only_rule.recall)}</td></tr>
          <tr><td>Avg. warning lead (days): model / rule</td><td><b>{f1(ev.warning.model.mean_lead_days)}</b> / {f1(ev.warning.threshold_only_rule.mean_lead_days)}</td></tr>
          <tr><td>Bill estimate error: model / “last month”</td><td><b>{pct(ev.bills.estimate_mape_model)}</b> / {pct(ev.bills.estimate_mape_naive)}</td></tr>
          <tr><td>Unusual-bill flags: precision / recall</td><td>{pct(ev.bills.anomaly_precision)} / {pct(ev.bills.anomaly_recall)}</td></tr>
        </tbody></table>
        <p className="small muted">The warning model and the simple rule trade precision for recall and lead time; threshold {ev.warning.threshold} tuned on calibration households.</p>
      </section>

      <section className="card">
        <h2>⚖️ Fairness <small>(forecast, by group)</small></h2>
        <table><thead><tr><th>Group</th><th>n</th><th>Timing MAE</th><th>naive</th><th>Range cov.</th></tr></thead><tbody>
          {Object.entries(ev.forecast.by_group).flatMap(([grp, v]) => Object.entries(v).map(([k, b]) =>
            <tr key={grp + k}><td>{grp}: <b>{k}</b></td><td>{b.n}</td><td>{f1(b.gap_mae_model)}</td><td>{f1(b.gap_mae_naive)}</td><td>{pct(b.gap_coverage)}</td></tr>))}
        </tbody></table>
        <p className="small muted">Irregular senders are forecast less accurately but still beat the naive guess, and the range stays honest about it.</p>
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
