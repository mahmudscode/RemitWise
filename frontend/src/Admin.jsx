import { useEffect, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDate, pct, taka } from './api'
import { GUIDED } from './Guided.jsx'

const COMPLIANCE = [0.6, 0.8, 1.0]
const f1 = (x) => (x == null ? '–' : (Math.round(x * 10) / 10).toFixed(1))
const TABS = [['overview', 'Overview'], ['users', 'Users'], ['model', 'Model performance'], ['monitor', 'Monitoring'], ['sim', 'Simulation sandbox'], ['audit', 'Audit & data']]
const EV = {
  arrival: (e) => [`Remittance ${taka(e.amount)} received`, 'var(--green)'], auto_skip: () => ['Plan skipped (money added to wallet)', 'var(--muted)'],
  bill_paid: (e) => [`${e.name} ${taka(e.amount)} auto-paid`, 'var(--primary)'], bill_paid_late: (e) => [`${e.name} paid late`, 'var(--amber)'],
  bill_needs_review: (e) => [`${e.name} ${taka(e.amount)} flagged: held for review`, 'var(--red)'], bill_overdue: (e) => [`${e.name} overdue`, 'var(--red)'],
  bill_due_manual: (e) => [`${e.name} due (pay manually)`, 'var(--amber)'], shortfall: () => ['Shortfall day: essentials not fully covered', 'var(--amber)'],
  high_bill_injected: (e) => [`Scenario: unusually high ${e.name} bill injected`, 'var(--red)'], large_expense: (e) => [`Scenario: large expense ${taka(e.amount)}`, 'var(--amber)'],
  eid_surge: (e) => [`Scenario: Eid expense surge until ${fmtDate(e.until)}`, 'var(--amber)'], medical_emergency: (e) => [`Scenario: medical emergency ${taka(e.amount)}`, 'var(--red)'],
  micro_paused: () => ['Micro-savings paused to protect bills', 'var(--amber)'], micro_resumed: () => ['Micro-savings resumed', 'var(--green)'],
  micro_on: () => ['Micro-savings switched on by the family', 'var(--primary)'], micro_off: () => ['Micro-savings switched off', 'var(--muted)'],
  systemic_shock: () => ['Scenario: systemic shock, next transfers delayed and smaller', 'var(--red)'],
  goal_used: (e) => [`Goal money used: ${taka(e.amount)}`, 'var(--amber)'],
}
const CHECKS = ['Synthetic data only', 'Feature explanations on every forecast', 'Auto-pay only under family mandates', 'Human confirmation above limits', 'LLM explains, never decides', 'Prompt-injection guard', 'Consent-based sharing with sender', 'Admins see aggregates, never a family\'s finances']

export default function Admin({ hid, state, act, tick, person, go, hh, setHid, logout, me, guided }) {
  const [tab, setTab] = useState('overview')
  const [ov, setOv] = useState(null)
  const [users, setUsers] = useState([])
  const [ev, setEv] = useState(null)
  const comp = 0.8 // compliance level used for the headline tiles and per-household line
  const [per, setPer] = useState([])
  const [audit, setAudit] = useState([])
  const [card, setCard] = useState('')
  const [msg, setMsg] = useState('')
  const [more, setMore] = useState(false)
  const [err, setErr] = useState('')

  const loadUsers = () => api('/admin/users').then(setUsers).catch((e) => setErr(e.message))
  useEffect(() => { api('/admin/overview').then(setOv).catch((e) => setErr(e.message)); loadUsers(); api('/evaluation').then(setEv).catch((e) => setErr(e.message)); api('/data-card').then((r) => setCard(r.markdown)).catch(() => {}) }, [tick])
  useEffect(() => { api(`/compare?household_id=${hid}&compliance=${comp}`).then(setPer).catch(() => setPer([])) }, [hid, comp])
  useEffect(() => { api('/audit?limit=30').then(setAudit).catch(() => {}) }, [tick])

  const run = (fn, ok) => act(async () => { setMsg(''); try { await fn(); if (ok) setMsg(ok) } catch (e) { setMsg(e.message) } }).catch(() => {})
  const scen = (kind, value = 0, ok) => run(() => api(`/households/${hid}/scenario`, { method: 'POST', body: { kind, value } }), ok)
  const adv = (d, to_arrival = false) => run(() => api(`/households/${hid}/advance`, { method: 'POST', body: { days: d, to_arrival } }))
  const delUser = async (u) => { if (!window.confirm(`Delete ${u.name}? This permanently removes the account and its goals.`)) return; try { await api(`/admin/users/${u.id}`, { method: 'DELETE' }); loadUsers(); api('/admin/overview').then(setOv) } catch (e) { setErr(e.message) } }
  const setStatus = async (u, active) => { try { await api(`/admin/users/${u.id}/status`, { method: 'POST', body: { active } }); loadUsers(); api('/admin/overview').then(setOv) } catch (e) { setErr(e.message) } }

  return (
    <div>
      <div className="topbar navy">
        <div className="row"><b style={{ fontSize: 20 }}>RemitWise</b><span className="badge">Admin console</span></div>
        <div className="row wrap"><span className="small only-desktop" style={{ opacity: .85 }}>{me?.name} · synthetic data only</span>
          <button className="btn sm" style={{ background: 'transparent', color: '#fff', borderColor: 'rgba(255,255,255,.5)' }} onClick={() => go('home')}>Open family app</button>
          <button className="btn sm" style={{ background: 'transparent', color: '#fff', borderColor: 'rgba(255,255,255,.5)' }} onClick={logout}>Log out</button></div>
      </div>
      <div className="admintabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
      <div className="adminwrap">
        {err && <div className="error" onClick={() => setErr('')}>{err}</div>}
        {tab === 'overview' && <Overview ov={ov} ev={ev} />}
        {tab === 'users' && <Users users={users} me={me} setStatus={setStatus} delUser={delUser} />}
        {tab === 'model' && ev && <Model ev={ev} comp={comp} per={per} person={person} />}
        {tab === 'monitor' && <Monitoring />}
        {tab === 'sim' && <Sim {...{ hid, hh, setHid, state, person, adv, scen, run, msg, more, setMore, go, guided }} />}
        {tab === 'audit' && <AuditTab audit={audit} card={card} />}
      </div>
    </div>
  )
}

const Tile = ({ label, value, foot, tone }) => <section className="card tile"><small>{label}</small><b className={tone}>{value}</b>{foot && <span className="foot">{foot}</span>}</section>

function Overview({ ov, ev }) {
  if (!ov) return <p className="muted">Loading…</p>
  const a = ov.accounts, h = ov.households, p = ov.plans, b = ov.bills, s = ov.system
  return (
    <div className="stackv">
      <div><h1 style={{ fontSize: 24 }}>Platform overview</h1><p className="muted small">{ov.privacy}</p></div>
      <div className="grid4 tiles">
        <Tile label="Registered families" value={a.families} foot={`${a.new_last_7_days} new in 7 days`} tone="txt-blue" />
        <Tile label="Linked senders" value={a.senders} foot={`${a.disabled} accounts disabled`} tone="txt-purple" />
        <Tile label="Households in use" value={h.in_use} foot={`${h.free} free of ${h.total} synthetic`} tone="txt-green" />
        <Tile label="Plans followed" value={p.followed_rate == null ? '–' : pct(p.followed_rate)} foot={`${p.accepted} accepted · ${p.edited} edited · ${p.skipped} skipped`} tone="txt-amber" />
      </div>
      <p className="tiny muted" style={{ marginBottom: -6 }}>Bill and shortfall figures below cover {b.scope}.</p>
      <div className="grid4 tiles">
        <Tile label="Bills paid on time" value={b.paid_on_time_rate == null ? '–' : pct(b.paid_on_time_rate)} foot={`${b.bills_due} bills processed`} tone="txt-green" />
        <Tile label="Late fees avoided" value={taka(b.late_fees_avoided)} foot={`${taka(b.late_fees_paid)} still paid`} tone="txt-blue" />
        <Tile label="Unusual bills caught" value={b.unusual_bills_caught} foot="held for family review" tone="txt-red" />
        <Tile label="Shortfall days" value={b.shortfall_days} foot={`across ${b.scope}`} tone="txt-amber" />
      </div>
      <div className="grid2e">
        <section className="card"><h2 style={{ marginBottom: 8 }}>Recent activity</h2>
          {ov.activity.length === 0 && <p className="muted small">No activity yet.</p>}
          {ov.activity.map((x) => <div className="row between small" key={x.action} style={{ padding: '4px 0' }}><span>{x.action.replace(/_/g, ' ')}</span><b>{x.count}</b></div>)}
          <p className="tiny muted" style={{ marginTop: 8 }}>Counts of the most recent 2,000 events. No personal details.</p></section>
        <section className="card"><h2 style={{ marginBottom: 8 }}>System</h2>
          {[['Database', s.database], ['Forecast model', s.model], ['AI explanations', s.llm_configured ? `Groq · ${s.llm_model}` : 'Built-in templates (no API key)'], ['Trained on', `${s.households_trained_on ?? '–'} synthetic households (seed ${s.data_seed})`], ['Last evaluation', s.trained_at ? s.trained_at.replace('T', ' ') : '–']].map(([k, v]) => <div className="row between small" key={k} style={{ padding: '5px 0', borderTop: '1px solid var(--line)' }}><span className="muted">{k}</span><b style={{ textAlign: 'right' }}>{v}</b></div>)}
        </section>
      </div>
      {ev && <section className="card info small">Model health at a glance: forecast timing error <b>{f1(ev.forecast.overall.gap_mae_model)} days</b> vs <b>{f1(ev.forecast.overall.gap_mae_naive)}</b> for the naive guess; range coverage {pct(ev.forecast.overall.gap_coverage)} (target 80%). See the Model performance tab.</section>}
    </div>
  )
}

function Users({ users, me, setStatus, delUser }) {
  const [q, setQ] = useState('')
  const rows = users.filter((u) => `${u.name} ${u.email} ${u.role}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="stackv">
      <div className="row between wrap"><div><h1 style={{ fontSize: 24 }}>Users</h1><p className="muted small">Emails are masked. You can disable an account (it is signed out everywhere) but cannot see its finances.</p></div>
        <input placeholder="Search name, email or role" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 280 }} /></div>
      <section className="card" style={{ overflowX: 'auto' }}>
        <table><thead><tr><th>Name</th><th>Role</th><th>Email</th><th>Joined</th><th>Status</th><th /></tr></thead><tbody>
          {rows.map((u) => (
            <tr key={u.id}><td><b>{u.name}</b>{u.is_demo && <span className="tag" style={{ marginLeft: 6 }}>demo</span>}</td>
              <td><span className={`chip ${u.role === 'family' ? 'blue' : u.role === 'sender' ? 'amber' : 'green'}`}>{u.role}</span></td>
              <td className="muted">{u.email}</td><td>{u.joined}</td>
              <td>{u.is_active ? <span className="chip green">Active</span> : <span className="chip red">Disabled</span>}</td>
              <td style={{ textAlign: 'right' }}>{u.id !== me?.id && (u.is_active ? <button className="btn sm redo" onClick={() => setStatus(u, false)}>Disable</button> : <button className="btn sm" onClick={() => setStatus(u, true)}>Enable</button>)}{u.id !== me?.id && !u.is_demo && <button className="btn sm redo" style={{ marginLeft: 8 }} onClick={() => delUser(u)}>Delete</button>}</td></tr>
          ))}
        </tbody></table>
        {rows.length === 0 && <p className="muted small" style={{ padding: 8 }}>No matching users.</p>}
      </section>
    </div>
  )
}

function Model({ ev, comp, per, person }) {
  const sum = ev.compare.summary
  const row = (policy, c) => sum.find((r) => r.policy === policy && (policy === 'baseline' || r.compliance === c))
  const base = row('baseline'), fx = row('fixed_rule', comp), rw = row('remitwise', comp)
  const o = ev.forecast.overall, w = ev.warning
  const mine = (p) => per.find((r) => r.policy === p)
  const samples = ev.forecast.samples.map((s, i) => ({ i: i + 1, actual: s.actual_gap, band: [s.model_p10, s.model_p90], model: s.model_p50, naive: s.naive }))
  const grp = ev.forecast.by_group
  const fair = [['Regular senders', grp.regularity.regular], ['Irregular senders', grp.regularity.irregular], ['Small transfers', grp.transfer_size.small], ['Rural households', grp.region.rural], ['Urban households', grp.region.urban]]
  const maxMae = Math.max(...fair.map(([, b]) => b.gap_mae_model))
  const metrics = [['Shortfall days / year', 'shortfall_days_per_year', f1], ['Bills paid on time', 'on_time_rate', pct], ['Late fees / year', 'late_fees_per_year', taka], ['Overbilling paid / year', 'overbilling_paid_per_year', taka], ['Savings rate', 'savings_rate', pct], ['Kept in wallet after 24h', 'retained_share', pct]]
  const honest = []
  if (fx.shortfall_days_per_year < rw.shortfall_days_per_year) honest.push(`A fixed 50/30/20 rule has fewer shortfall days (${f1(fx.shortfall_days_per_year)}) than RemitWise (${f1(rw.shortfall_days_per_year)}).`)
  else honest.push(`RemitWise has fewer shortfall days (${f1(rw.shortfall_days_per_year)}) than a fixed 50/30/20 rule (${f1(fx.shortfall_days_per_year)}).`)
  honest.push(`RemitWise leads on bills paid on time (${pct(rw.on_time_rate)} vs ${pct(fx.on_time_rate)} for the fixed rule and ${pct(base.on_time_rate)} with no plan) and on money kept in the wallet (${pct(rw.retained_share)} vs ${pct(fx.retained_share)}).`)
  return (
    <div className="stackv">
      <div className="row between wrap"><h1 style={{ fontSize: 24 }}>Model performance on held-out test set</h1><span className="small txt-green" style={{ fontWeight: 600 }}>Measured on {ev.compare.n_households} synthetic test households never used for training</span></div>
      <div className="grid4 tiles">
        <Tile label="Remittance timing error (MAE)" value={`${f1(o.gap_mae_model)} days`} foot={`Baseline: ${f1(o.gap_mae_naive)} days`} tone="txt-blue" />
        <Tile label="Shortfall warning precision / recall" value={`${w.model.precision.toFixed(2)} / ${w.model.recall.toFixed(2)}`} foot={`Simple rule: ${w.threshold_only_rule.precision.toFixed(2)} / ${w.threshold_only_rule.recall.toFixed(2)}`} tone="txt-purple" />
        <Tile label="On-time EMI & bill payments" value={pct(rw.on_time_rate)} foot={`Without plan: ${pct(base.on_time_rate)} · simulated`} tone="txt-green" />
        <Tile label="Late fees avoided" value={taka(base.late_fees_per_year - rw.late_fees_per_year)} foot={`per household / year · simulated, ${pct(comp)} compliance`} tone="txt-amber" />
      </div>
      <div className="grid2e" style={{ gridTemplateColumns: '1.5fr 1fr' }}>
        <section className="card">
          <div className="row between"><h2>Days until next transfer: forecast vs actual</h2><span className="ai">Test set</span></div>
          <div style={{ height: 250 }}><ResponsiveContainer><ComposedChart data={samples}>
            <CartesianGrid vertical={false} stroke="#eef2f6" /><XAxis dataKey="i" fontSize={11} tickLine={false} /><YAxis fontSize={11} width={30} tickLine={false} axisLine={false} /><Tooltip /><Legend />
            <Area isAnimationActive={false} dataKey="band" name="Model 80% range" stroke="none" fill="#0d56a5" fillOpacity={0.12} />
            <Line isAnimationActive={false} dataKey="actual" name="Actual" stroke="#0a3d7a" dot={false} strokeWidth={2} />
            <Line isAnimationActive={false} dataKey="model" name="RemitWise model" stroke="#0d56a5" dot={false} strokeWidth={2.5} />
            <Line isAnimationActive={false} dataKey="naive" name="Baseline (same as last time)" stroke="#8a97a5" dot={false} strokeDasharray="5 4" />
          </ComposedChart></ResponsiveContainer></div>
          <p className="tiny muted">60 random test cases sorted by actual gap. The model's range covers about {pct(o.gap_coverage)} of outcomes.</p>
        </section>
        <section className="card">
          <div className="row between"><h2>Fairness check</h2><span className="tiny muted">Timing MAE by group</span></div>
          {fair.map(([label, b]) => (
            <div className="barrow" key={label}><div className="row between small"><span>{label}</span><b className={b.gap_mae_model > 0.7 * maxMae ? 'txt-amber' : 'txt-green'}>{f1(b.gap_mae_model)} days</b></div>
              <div className="hbar"><div style={{ width: `${(b.gap_mae_model / maxMae) * 100}%`, background: b.gap_mae_model > 0.7 * maxMae ? 'var(--amber)' : 'var(--green)' }} /></div></div>))}
          <p className="tiny muted" style={{ marginTop: 8 }}>Irregular senders are harder to predict, so warnings for them use wider ranges.</p>
        </section>
      </div>
      <section className="card">
        <h2>A simulated year, with vs without RemitWise</h2>
        <div className="simbanner"><b>Simulated, not measured.</b> Compliance is an assumption; a real pilot would measure it.</div>
        <p className="small muted" style={{ margin: '6px 0' }}>Compliance = the share of transfer cycles in which the family follows the plan. All three levels are shown so the result cannot be cherry-picked.</p>
        <div style={{ overflowX: 'auto' }}><table><thead><tr><th>Average over test households</th><th>No plan</th><th>Fixed 50/30/20 ({pct(comp)})</th>{COMPLIANCE.map((c) => <th key={c}>RemitWise {pct(c)}</th>)}</tr></thead>
          <tbody>{metrics.map(([label, k, fmt]) => <tr key={k}><td>{label}</td><td>{fmt(base[k])}</td><td>{fmt(fx[k])}</td>{COMPLIANCE.map((c) => <td key={c}><b>{fmt(row('remitwise', c)[k])}</b></td>)}</tr>)}</tbody></table></div>
        <p className="small" style={{ marginTop: 8 }}><b>Honest reading ({pct(comp)} compliance):</b> {honest.join(' ')}</p>
        {mine('baseline') && mine('remitwise') && <p className="small" style={{ marginTop: 6 }}>For <b>{person?.name}</b> alone ({pct(comp)}): {f1(mine('baseline').shortfall_days_per_year)} shortfall days a year without → <b>{f1(mine('remitwise').shortfall_days_per_year)}</b> with RemitWise; bills on time {pct(mine('baseline').on_time_rate)} → <b>{pct(mine('remitwise').on_time_rate)}</b>.</p>}
      </section>
      <WarningTuning w={w} />
      {ev.stress && <StressTest st={ev.stress} />}
      {ev.live_model && <LiveModel lm={ev.live_model} />}
      {ev.sequence_experiment && <SequenceExperiment x={ev.sequence_experiment} />}
      {ev.adaptive && <AdaptiveExperiment a={ev.adaptive} />}
      {ev.irregular_experiment && <IrregularExperiment x={ev.irregular_experiment} />}
      {ev.kpi_base && <Kpis ev={ev} />}
      <section className="card">
        <h2 style={{ marginBottom: 10 }}>Responsible AI checks</h2>
        <div className="chiprow">{CHECKS.map((c) => <span className="okchip" key={c}>✓ {c}</span>)}</div>
        <p className="small muted" style={{ marginTop: 10 }}>Bill estimate error {pct(ev.bills.estimate_mape_model)} vs {pct(ev.bills.estimate_mape_naive)} for “same as last month”; unusual-bill flags precision {pct(ev.bills.anomaly_precision)}, recall {pct(ev.bills.anomaly_recall)}. The tuned warning model trades some recall for far fewer false alarms; see the threshold table above.</p>
      </section>
    </div>
  )
}

function WarningTuning({ w }) {
  if (!w.before || !w.after) return null
  const rule = w.threshold_only_rule
  const rows = [['Before (model only, best F1)', w.before, true], ['Model only, precision-tuned', w.model_only, true], ['After: hybrid (model OR simple rule)', w.after, true], ['Simple rule (no model)', rule, false]].filter((r) => r[1])
  const ld = (x) => (x == null ? '–' : `${x.toFixed(1)} days`)
  return (
    <section className="card">
      <div className="row between wrap"><h2>Warning threshold: before vs after</h2><span className="ai">Test set</span></div>
      <p className="small muted" style={{ margin: '6px 0' }}>The threshold is chosen on calibration households only, then measured on {w.after.n.toLocaleString()} checkpoints from the held-out test households. {w.after.selection && <>After: {w.after.selection}.</>}</p>
      <table><thead><tr><th>Setting</th><th>Threshold</th><th>Precision</th><th>Recall</th><th>F1</th><th>Avg. warning lead</th></tr></thead>
        <tbody>{rows.map(([label, m, hasT]) => <tr key={label}><td>{label}</td><td>{hasT ? m.threshold.toFixed(2) : '–'}</td><td><b>{m.precision.toFixed(2)}</b></td><td>{m.recall.toFixed(2)}</td><td>{m.f1.toFixed(2)}</td><td>{ld(m.mean_lead_days)}</td></tr>)}</tbody></table>
      <div style={{ height: 230, marginTop: 12 }}><ResponsiveContainer><ComposedChart data={w.sweep}>
        <CartesianGrid vertical={false} stroke="#eef2f6" /><XAxis dataKey="threshold" fontSize={11} tickLine={false} /><YAxis domain={[0, 1]} fontSize={11} width={30} tickLine={false} axisLine={false} /><Tooltip /><Legend />
        <Line isAnimationActive={false} dataKey="precision" name="Precision" stroke="#0d56a5" strokeWidth={2.5} dot={false} />
        <Line isAnimationActive={false} dataKey="recall" name="Recall" stroke="#c77d0a" strokeWidth={2.5} dot={false} />
        <ReferenceLine x={w.after.threshold} stroke="#0a3d7a" strokeDasharray="4 3" label={{ value: 'chosen', fontSize: 11, position: 'top' }} />
      </ComposedChart></ResponsiveContainer></div>
      <p className="small" style={{ marginTop: 6 }}><b>Honest reading:</b> Higher precision means fewer false alarms but some shortfalls are caught later or missed. The hybrid warns when the model is confident or the simple rule fires: it catches more shortfalls and earlier than the rule alone, at a few points less precision than the rule. The chart shows the hybrid.</p>
    </section>
  )
}

function Guided({ guided }) {
  const last = guided.last
  const step = (n) => guided.run(n)
  return (
    <section className="card">
      <h2>Guided demo</h2>
      <p className="small muted" style={{ margin: '6px 0 10px' }}>The judge path on the selected household. Press <b>Reset household</b> below, then 1 to 5 in order. Each step opens the family screen it is about; use “Back to admin console” in the sidebar to continue.</p>
      <div className="guided">
        {GUIDED.map(([title, hint], i) => (
          <button key={title} className={`btn block step ${last === i + 1 ? 'primary' : ''}`} onClick={() => step(i + 1)} title={hint}>
            <span className="num">{i + 1}</span><span><b>{title}</b><br /><small style={{ fontWeight: 400, opacity: .85 }}>{hint}</small></span>
          </button>
        ))}
      </div>
    </section>
  )
}

const KPI_DEFAULTS = { compliance: 0.8, walletBase: 35, fee: 5, daysHeld: 15, floatRate: 4 }

function Kpis({ ev }) {
  const [a, setA] = useState(KPI_DEFAULTS)
  const num = (k) => (e) => setA({ ...a, [k]: e.target.value === '' ? '' : +e.target.value })
  const sum = ev.compare.summary
  const base = sum.find((r) => r.policy === 'baseline')
  const rw = sum.find((r) => r.policy === 'remitwise' && r.compliance === +a.compliance)
  const kb = ev.kpi_base
  const n = (x) => +x || 0
  // every number below is multiplied out from the visible inputs; nothing is hidden
  const payBase = kb.bills_per_household_month * n(a.walletBase) / 100
  const payRw = kb.bills_per_household_month * +a.compliance  // plan followed => bills run through wallet auto-pay
  const extraPay = Math.max(payRw - payBase, 0)
  const feeYear = extraPay * n(a.fee) * 12
  const extraKept = (rw.retained_share - base.retained_share) * kb.monthly_remittance
  const floatYear = extraKept * 12 * (n(a.daysHeld) / 365) * (n(a.floatRate) / 100)
  const rows = [
    ['Kept in wallet after 24h', pct(base.retained_share), pct(rw.retained_share), `${taka(extraKept)} more per household per month`],
    ['Digital bill payments / household / month', payBase.toFixed(1), payRw.toFixed(1), `+${extraPay.toFixed(1)} payments`],
    ['Savings rate', pct(base.savings_rate), pct(rw.savings_rate), 'share of income saved'],
    ['Bills paid on time', pct(base.on_time_rate), pct(rw.on_time_rate), 'fewer late fees for the family'],
  ]
  const field = (k, label, unit) => <label className="small" key={k}>{label}<div className="row"><input type="number" min="0" step="any" value={a[k]} onChange={num(k)} style={{ maxWidth: 110 }} /><span className="muted">{unit}</span></div></label>
  return (
    <section className="card">
      <div className="row between wrap"><h2>Business KPIs (simulated)</h2><span className="ai">Simulated</span></div>
      <div className="simbanner"><b>Simulated estimate.</b> A controlled pilot would measure these. Edit any assumption below; nothing is hidden.</div>
      <div className="row wrap" style={{ gap: 14, margin: '8px 0' }}>
        <label className="small">Plan followed in<div><select value={a.compliance} onChange={(e) => setA({ ...a, compliance: +e.target.value })}>{[0.6, 0.8, 1.0].map((c) => <option key={c} value={c}>{pct(c)} of cycles</option>)}</select></div></label>
        {field('walletBase', 'Bills paid via wallet today (no plan)', '%')}
        {field('fee', 'Fee per bill payment', '৳')}
        {field('daysHeld', 'Days a kept taka stays in wallet', 'days')}
        {field('floatRate', 'Value of held money', '% / year')}
      </div>
      <table><thead><tr><th>KPI</th><th>No plan</th><th>With RemitWise</th><th>Difference</th></tr></thead>
        <tbody>{rows.map(([k, x, y, d]) => <tr key={k}><td>{k}</td><td>{x}</td><td><b>{y}</b></td><td className="muted">{d}</td></tr>)}
          <tr><td>Customer retention</td><td colSpan="3" className="muted">Not simulated. Only a pilot can measure whether families stay longer.</td></tr></tbody></table>
      <p style={{ marginTop: 10 }}><b>Illustrative incremental value per household per year: {taka(feeYear + floatYear)}</b>
        <span className="muted small"> = bill-payment fees {taka(feeYear)} ({extraPay.toFixed(1)} extra payments × ৳{n(a.fee)} × 12) + value of held money {taka(floatYear)} ({taka(extraKept)} × 12 × {n(a.daysHeld)}/365 × {n(a.floatRate)}%)</span></p>
      <p className="tiny muted" style={{ marginTop: 6 }}>Volumes come from {kb.households} synthetic test households ({kb.bills_per_household_month} bills and {taka(kb.monthly_remittance)} of remittances per household per month). See docs/pilot-plan.md for how a randomized pilot would measure the real effect.</p>
    </section>
  )
}

function Monitoring() {
  const [m, setM] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api('/admin/monitoring').then(setM).catch((e) => setErr(e.message)) }, [])
  if (err) return <div className="error">{err}</div>
  if (!m) return <p className="muted">Loading…</p>
  const o = m.overall, wr = m.warning_rate
  const tone = (ok) => (ok ? 'txt-green' : 'txt-red')
  return (
    <div className="stackv">
      <div><h1 style={{ fontSize: 24 }}>Model monitoring</h1><p className="muted small">{m.window.note} {m.window.cycles.toLocaleString()} transfers from {m.window.households} households.</p></div>
      {m.alerts.length > 0
        ? <section className="card red"><h2 className="txt-red">🚩 {m.alerts.length} flag{m.alerts.length > 1 ? 's' : ''} to review</h2><ul className="why small">{m.alerts.map((a) => <li key={a}>{a}</li>)}</ul></section>
        : <section className="card green"><h2 className="txt-green">No flags: coverage and error are within limits.</h2></section>}
      <div className="grid4 tiles">
        <Tile label="Timing error (MAE)" value={`${f1(o.gap_mae)} days`} foot="recent window" tone="txt-blue" />
        <Tile label="Timing range coverage" value={pct(o.gap_coverage)} foot={`target 80%, flag below ${pct(m.thresholds.min_coverage)}`} tone={tone(o.gap_coverage >= m.thresholds.min_coverage)} />
        <Tile label="Amount range coverage" value={pct(o.amt_coverage)} foot={`amount error ${pct(o.amt_mape)}`} tone={tone(o.amt_coverage >= m.thresholds.min_coverage)} />
        <Tile label="Warning rate now" value={wr?.rate == null ? '–' : pct(wr.rate)} foot={wr ? `${wr.amber + wr.red} of ${wr.households} active households amber or red` : ''} tone="txt-amber" />
      </div>
      <section className="card">
        <h2>Rolling error (30-day periods)</h2>
        <div style={{ height: 220 }}><ResponsiveContainer><ComposedChart data={m.rolling}>
          <CartesianGrid vertical={false} stroke="#eef2f6" /><XAxis dataKey="period" fontSize={11} tickLine={false} /><YAxis yAxisId="l" fontSize={11} width={30} tickLine={false} axisLine={false} /><YAxis yAxisId="r" orientation="right" domain={[0.5, 1]} fontSize={11} width={36} tickLine={false} axisLine={false} tickFormatter={(v) => pct(v)} /><Tooltip /><Legend />
          <Line yAxisId="l" isAnimationActive={false} dataKey="gap_mae" name="Timing error (days)" stroke="#0d56a5" strokeWidth={2.5} dot={false} />
          <Line yAxisId="r" isAnimationActive={false} dataKey="gap_coverage" name="Timing coverage" stroke="#1e9e63" strokeWidth={2.5} dot={false} />
          <ReferenceLine yAxisId="r" y={m.thresholds.min_coverage} stroke="#d14343" strokeDasharray="4 3" />
        </ComposedChart></ResponsiveContainer></div>
      </section>
      <div className="grid2e">
        <section className="card" style={{ overflowX: 'auto' }}>
          <h2>Fairness by group</h2>
          <table><thead><tr><th>Group</th><th>Transfers</th><th>Timing error</th><th>Coverage</th><th /></tr></thead><tbody>
            {m.groups.map((g) => <tr key={g.dimension + g.group}><td>{g.group} <span className="tiny muted">({g.dimension.toLowerCase()})</span></td><td>{g.n}</td><td>{f1(g.gap_mae)} d</td><td className={tone(g.gap_coverage >= m.thresholds.min_coverage)}>{pct(g.gap_coverage)}</td><td>{g.flags.length ? <span className="chip red">🚩 flag</span> : <span className="chip green">ok</span>}</td></tr>)}
          </tbody></table>
          <p className="tiny muted" style={{ marginTop: 6 }}>Flag: coverage below {pct(m.thresholds.min_coverage)}, or timing error above {m.thresholds.error_ratio}× the other groups.</p>
        </section>
        <section className="card" style={{ overflowX: 'auto' }}>
          <h2>Input drift vs training data</h2>
          <table><thead><tr><th>Feature</th><th>PSI</th><th>Mean shift</th><th /></tr></thead><tbody>
            {m.drift.map((d) => <tr key={d.feature}><td>{d.feature.replace(/_/g, ' ')}</td><td>{d.psi ?? '–'}</td><td>{d.mean_shift_sd > 0 ? '+' : ''}{d.mean_shift_sd} sd</td><td><span className={`chip ${d.status === 'alert' ? 'red' : d.status === 'watch' ? 'amber' : 'green'}`}>{d.status}</span></td></tr>)}
          </tbody></table>
          <p className="tiny muted" style={{ marginTop: 6 }}>PSI under {m.thresholds.psi_watch} is stable; over {m.thresholds.psi_alert} means the inputs have shifted.</p>
        </section>
      </div>
      <section className="card info small">{m.note} Irregular senders are the group to watch: the model is least certain about them, which is also why their ranges are wider.</section>
    </div>
  )
}

const Status = ({ x, on = 'Adopted' }) => <span className={`chip ${x.adopted ? 'green' : x.forced ? 'blue' : 'amber'}`}>{x.adopted ? on : x.forced ? 'On by team decision' : 'Not adopted'}</span>

function LiveModel({ lm }) {
  const b = lm.baseline, l = lm.live
  const rows = [['Timing error', `${f1(b.gap_mae)} d`, `${f1(l.gap_mae)} d`], ['Timing range coverage', pct(b.gap_coverage), pct(l.gap_coverage)], ['Amount error', pct(b.amt_mape), pct(l.amt_mape)], ['Amount range coverage', pct(b.amt_coverage), pct(l.amt_coverage)],
    ...Object.keys(b.by_regularity).map((g) => [`${g[0].toUpperCase()}${g.slice(1)} senders: timing error`, `${f1(b.by_regularity[g].gap_mae)} d`, `${f1(l.by_regularity[g].gap_mae)} d`])]
  return (
    <section className="card">
      <div className="row between wrap"><h2>The model serving the app</h2><span className="ai">Test set</span></div>
      <p className="small muted" style={{ margin: '6px 0' }}>{lm.description}. {lm.n_features} input features.</p>
      <table><thead><tr><th>Measure</th><th>Original baseline</th><th>Live model</th></tr></thead><tbody>{rows.map(([k, x, y]) => <tr key={k}><td>{k}</td><td>{x}</td><td><b>{y}</b></td></tr>)}</tbody></table>
      <p className="small" style={{ marginTop: 8 }}><b>Honest reading:</b> the experiments below did not improve accuracy on this synthetic data. They are switched on by team decision (<code>FORCE_*</code> settings) and cost nothing measurable here; the household correction does cost accuracy and is labelled as such.</p>
    </section>
  )
}

function SequenceExperiment({ x }) {
  const names = [['baseline', 'Current LightGBM (live)'], ['lightgbm_temporal', 'LightGBM + lag/rolling features'], ['mlp_sequence', 'Neural net over last 6 gaps and 3 amounts']]
  return (
    <section className="card" style={{ overflowX: 'auto' }}>
      <div className="row between wrap"><h2>Experiment: temporal / sequence models</h2><Status x={x} on="A variant replaced the model" /></div>
      <p className="small muted" style={{ margin: '6px 0' }}>{x.description} Measured on the held-out test households.</p>
      <table><thead><tr><th>Model</th><th>Timing error</th><th>Timing coverage</th><th>Amount error</th><th>Amount coverage</th><th>Beats baseline?</th></tr></thead>
        <tbody>{names.map(([k, label]) => { const o = x[k].overall; const v = x.verdicts?.[k]
          return <tr key={k}><td>{label}</td><td><b>{f1(o.gap_mae_model)} d</b></td><td>{pct(o.gap_coverage)}</td><td>{pct(o.amt_mape_model)}</td><td>{pct(o.amt_coverage)}</td><td>{v ? (v.wins ? <span className="chip green">yes</span> : <span className="chip gray">no</span>) : '–'}</td></tr> })}</tbody></table>
      <p className="small" style={{ marginTop: 8 }}><b>Result:</b> {x.reason} The offline rule did not require a switch, and the temporal LightGBM features are on by team decision (no measurable change). The neural net predicts amounts slightly better but times transfers worse and its ranges cover less than 80%.</p>
    </section>
  )
}

function AdaptiveExperiment({ a }) {
  const rows = [['Overall', a.before.gap_mae, a.after.gap_mae, a.before.gap_coverage, a.after.gap_coverage],
    ...Object.keys(a.before.by_regularity).map((g) => [`${g[0].toUpperCase()}${g.slice(1)} senders`, a.before.by_regularity[g].gap_mae, a.after.by_regularity[g].gap_mae, a.before.by_regularity[g].gap_coverage, a.after.by_regularity[g].gap_coverage])]
  return (
    <section className="card" style={{ overflowX: 'auto' }}>
      <div className="row between wrap"><h2>Experiment: adaptive household correction</h2><Status x={a} on="Live in the app" /></div>
      <p className="small muted" style={{ margin: '6px 0' }}>{a.description}</p>
      <table><thead><tr><th>Group</th><th>Timing error without</th><th>with correction</th><th>Coverage without</th><th>with correction</th></tr></thead>
        <tbody>{rows.map(([k, b, x, cb, cx]) => <tr key={k}><td>{k}</td><td>{f1(b)} d</td><td><b>{f1(x)} d</b></td><td>{pct(cb)}</td><td>{pct(cx)}</td></tr>)}</tbody></table>
      <p className="small" style={{ marginTop: 8 }}><b>Result:</b> {a.reason} In this synthetic data a household's gaps are independent draws, so earlier misses carry no signal and the correction only adds noise. It is on by team decision and makes timing error worse here (see the table); set <code>FORCE_ADAPTIVE=false</code> to turn it off. With real remittance behaviour it may help, which a pilot would test. The spending baseline is already adaptive: daily needs are re-estimated from the last 60 days.</p>
    </section>
  )
}

function IrregularExperiment({ x }) {
  const names = [['baseline', 'Current model'], ['regularity_features', '+ regularity features'], ['regularity_features_group_calibration', '+ regularity features and group calibration']]
  return (
    <section className="card" style={{ overflowX: 'auto' }}>
      <div className="row between wrap"><h2>Experiment: better forecasts for irregular senders</h2><Status x={x} /></div>
      <p className="small muted" style={{ margin: '6px 0' }}>{x.description} Measured on the held-out test households.</p>
      <table><thead><tr><th>Variant</th><th>Overall timing error</th><th>Overall coverage</th><th>Irregular timing error</th><th>Irregular coverage</th><th>Regular coverage</th></tr></thead>
        <tbody>{names.map(([k, label]) => { const o = x[k].overall, i = x[k].by_regularity.irregular, r = x[k].by_regularity.regular
          return <tr key={k}><td>{label}</td><td>{f1(o.gap_mae_model)} d</td><td>{pct(o.gap_coverage)}</td><td><b>{f1(i.gap_mae_model)} d</b></td><td>{pct(i.gap_coverage)}</td><td>{pct(r.gap_coverage)}</td></tr> })}</tbody></table>
      <p className="small" style={{ marginTop: 8 }}><b>Result:</b> {x.reason} Irregular senders stay the hardest group to predict; their ranges are wider for that reason, and the fairness panel keeps watching them.</p>
    </section>
  )
}

function StressTest({ st }) {
  const f = st.forecast, w = st.warning
  const row = (label, a, b, fmt = (x) => x.toFixed(2)) => <tr key={label}><td>{label}</td><td>{fmt(a)}</td><td><b>{fmt(b)}</b></td></tr>
  return (
    <section className="card">
      <div className="row between wrap"><h2>Stress test: systemic shock</h2><span className="ai">Test set</span></div>
      <p className="small muted" style={{ margin: '6px 0' }}>{st.description} Same shock as the sandbox button “Systemic shock”.</p>
      <table><thead><tr><th>Measure</th><th>Normal</th><th>Under shock</th></tr></thead><tbody>
        {row('Timing error (MAE, days)', f.normal.gap_mae, f.shock.gap_mae, (x) => x.toFixed(1))}
        {row('Timing range coverage (target 80%)', f.normal.gap_coverage, f.shock.gap_coverage, pct)}
        {row('Amount range coverage', f.normal.amt_coverage, f.shock.amt_coverage, pct)}
        {row('Warning precision', w.normal.precision, w.shock.precision)}
        {row('Warning recall', w.normal.recall, w.shock.recall)}
        {row('Average warning lead (days)', w.normal.mean_lead_days, w.shock.mean_lead_days, (x) => x.toFixed(1))}
        {row('Share of cycles that end in a shortfall', w.normal.base_rate, w.shock.base_rate, pct)}
      </tbody></table>
      <p className="small" style={{ marginTop: 8 }}><b>Honest reading:</b> {st.note} Forecast ranges lose most of their coverage because the model has never seen a shock. Warnings still fire, but give less notice. A real deployment would add a corridor-level alert and retrain on shock periods.</p>
    </section>
  )
}

function Sim({ hid, hh, setHid, state, person, adv, scen, run, msg, more, setMore, go, guided }) {
  const events = [...state.log].reverse().filter((e) => EV[e.type]).slice(0, 10)
  return (
    <div className="simwrap" style={{ padding: 0 }}>
      <div className="stackv" style={{ alignSelf: 'start' }}>
        <Guided guided={guided} />
        <section className="card">
          <h2>Simulation sandbox</h2>
          <p className="small muted" style={{ margin: '6px 0' }}>Try situations on synthetic demo households before they could ever touch a real family. Real accounts are never affected.</p>
          <p className="small muted" style={{ margin: '8px 0 4px' }}>Household</p>
          <select value={hid} onChange={(e) => setHid(e.target.value)}>{hh.map((h) => <option key={h.household_id} value={h.household_id}>{h.household_id} · {h.name} family · {h.regularity_class} sender</option>)}</select>
          <p className="small muted" style={{ margin: '8px 0 10px' }}>Simulated date: {fmtDate(state.date)} {state.date.slice(0, 4)}</p>
          <div className="stackv" style={{ gap: 8 }}>
            <button className="btn primary block" onClick={() => adv(1, true)}>Trigger remittance</button>
            <button className="btn block" onClick={() => adv(7)}>Advance 7 days</button>
            <p className="small" style={{ margin: '6px 0 0', fontWeight: 700 }}>Real-life scenarios</p>
            <button className="btn block" onClick={() => scen('delay', 14, 'Next transfer delayed by 14 days.')}>Delay next transfer</button>
            <button className="btn block" onClick={() => scen('eid_surge', 0, 'Eid expense surge: daily needs about 40% higher for 10 days.')}>Eid expense surge</button>
            <button className="btn block" onClick={() => scen('systemic_shock', 0, 'Systemic shock: the next 3 transfers arrive 21 days later each and 30% smaller.')}>Systemic shock (corridor disruption)</button>
            <button className="btn block" onClick={() => scen('medical', 8000, 'Medical emergency: ৳8,000 unexpected expense.')}>Medical emergency</button>
            <button className="btn block" onClick={() => scen('high_bill', 0, 'The next electricity bill will be unusually high.')}>Inject unusually high bill (electricity)</button>
            <p className="small" style={{ margin: '6px 0 0', fontWeight: 700 }}>Other</p>
            <button className="btn block" onClick={() => scen('new_emi', 0, 'A new phone EMI mandate was added.')}>Add new EMI</button>
            <button className="btn block ghost" onClick={() => { guided.setLast(0); run(() => api(`/households/${hid}/reset`, { method: 'POST' }), 'Household reset.') }}>Reset household</button>
            <button className="link" onClick={() => setMore(!more)}>{more ? 'Fewer' : 'More'} scenarios</button>
            {more && <div className="stackv" style={{ gap: 8 }}>
              <button className="btn block sm" onClick={() => scen('expense', Math.round(state.monthly_needs * 0.5))}>Large expense</button>
              <button className="btn block sm" onClick={() => scen('second_income', 5000, 'Second income added.')}>Second income ৳5,000/month</button>
              <button className="btn block sm" onClick={() => scen('family_member', 0.15, 'Needs up 15%.')}>New family member (+15% needs)</button></div>}
            <button className="link" onClick={() => go('home')}>Open {person?.name}'s family app →</button>
          </div>
          {msg && <p className="small" style={{ marginTop: 8 }}>{msg}</p>}
          <p className="tiny muted" style={{ marginTop: 8 }}>The forecaster does not know about scenario events in advance.</p>
        </section>
      </div>
      <div className="stackv">
        <section className="card"><h2 style={{ marginBottom: 10 }}>Event log · {person?.name}</h2>
          <div className="evlog">{events.length === 0 && <span className="muted">No events yet. Trigger a remittance.</span>}
            {events.map((e, i) => { const [t, c] = EV[e.type](e); return <div key={i}><span className="t">{fmtDate(new Date(new Date(state.date + 'T00:00:00').getTime() - (state.day - e.day) * 86400000).toISOString().slice(0, 10))}</span><span style={{ color: c }}>{t}</span></div> })}
          </div></section>
        <section className="card info small">After you trigger something here, open the family app for this household to see how the interface reacts, then come back to check the event log and the Audit tab.</section>
      </div>
    </div>
  )
}

function AuditTab({ audit, card }) {
  const [show, setShow] = useState(false)
  return (
    <div className="stackv">
      <section className="card"><h2 style={{ marginBottom: 8 }}>Audit log <small className="muted">(demo households and system events)</small></h2>
        <ul className="why small" style={{ listStyle: 'none', paddingLeft: 0 }}>{audit.map((a, i) => <li key={i}>{a.ts.replace('T', ' ').slice(0, 19)} · <b>{a.actor}</b> · {a.action.replace(/_/g, ' ')} {a.household_id || ''}</li>)}</ul>
        <p className="tiny muted">Activity of registered families is not shown here.</p></section>
      <section className="card"><h2>Data card</h2><button className="link" onClick={() => setShow(!show)}>{show ? 'Hide' : 'Show'} assumptions</button>{show && <pre>{card}</pre>}</section>
    </div>
  )
}
