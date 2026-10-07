import { useEffect, useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDate, pct, taka } from './api'

const COMPLIANCE = [0.6, 0.8, 1.0]
const f1 = (x) => (x == null ? '–' : (Math.round(x * 10) / 10).toFixed(1))
const TABS = [['overview', 'Overview'], ['users', 'Users'], ['model', 'Model performance'], ['sim', 'Simulation sandbox'], ['audit', 'Audit & data']]
const EV = {
  arrival: (e) => [`Remittance ${taka(e.amount)} received`, 'var(--green)'], auto_skip: () => ['Plan skipped (money added to wallet)', 'var(--muted)'],
  bill_paid: (e) => [`${e.name} ${taka(e.amount)} auto-paid`, 'var(--primary)'], bill_paid_late: (e) => [`${e.name} paid late`, 'var(--amber)'],
  bill_needs_review: (e) => [`${e.name} ${taka(e.amount)} flagged: held for review`, 'var(--red)'], bill_overdue: (e) => [`${e.name} overdue`, 'var(--red)'],
  bill_due_manual: (e) => [`${e.name} due (pay manually)`, 'var(--amber)'], shortfall: () => ['Shortfall day: essentials not fully covered', 'var(--amber)'],
  high_bill_injected: (e) => [`Scenario: unusually high ${e.name} bill injected`, 'var(--red)'], large_expense: (e) => [`Scenario: large expense ${taka(e.amount)}`, 'var(--amber)'],
  eid_surge: (e) => [`Scenario: Eid expense surge until ${fmtDate(e.until)}`, 'var(--amber)'], medical_emergency: (e) => [`Scenario: medical emergency ${taka(e.amount)}`, 'var(--red)'],
  goal_used: (e) => [`Goal money used: ${taka(e.amount)}`, 'var(--amber)'],
}
const CHECKS = ['Synthetic data only', 'Feature explanations on every forecast', 'Auto-pay only under family mandates', 'Human confirmation above limits', 'LLM explains, never decides', 'Prompt-injection guard', 'Consent-based sharing with sender', 'Admins see aggregates, never a family\'s finances']

export default function Admin({ hid, state, act, tick, person, go, hh, setHid, logout, me }) {
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
        {tab === 'sim' && <Sim {...{ hid, hh, setHid, state, person, adv, scen, run, msg, more, setMore, go }} />}
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
  const rows = [['Before (best F1)', w.before, true], ['After (precision-tuned)', w.after, true], ['Simple rule (no model)', rule, false]]
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
      <p className="small" style={{ marginTop: 6 }}><b>Honest reading:</b> Higher precision means fewer false alarms but some shortfalls are caught later or missed.</p>
    </section>
  )
}

function Sim({ hid, hh, setHid, state, person, adv, scen, run, msg, more, setMore, go }) {
  const events = [...state.log].reverse().filter((e) => EV[e.type]).slice(0, 10)
  return (
    <div className="simwrap" style={{ padding: 0 }}>
      <div className="stackv" style={{ alignSelf: 'start' }}>
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
            <button className="btn block" onClick={() => scen('medical', 8000, 'Medical emergency: ৳8,000 unexpected expense.')}>Medical emergency</button>
            <button className="btn block" onClick={() => scen('high_bill', 0, 'The next electricity bill will be unusually high.')}>Inject unusually high bill (electricity)</button>
            <p className="small" style={{ margin: '6px 0 0', fontWeight: 700 }}>Other</p>
            <button className="btn block" onClick={() => scen('new_emi', 0, 'A new phone EMI mandate was added.')}>Add new EMI</button>
            <button className="btn block ghost" onClick={() => run(() => api(`/households/${hid}/reset`, { method: 'POST' }), 'Household reset.')}>Reset household</button>
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
