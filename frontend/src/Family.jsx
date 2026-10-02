import { useEffect, useRef, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDate, pct, taka } from './api'

const SEV = { green: 'On track', amber: 'Watch closely', red: 'Likely to run short' }

export default function Family({ hid, state, lang, t, role, user, act, tick }) {
  const [fc, setFc] = useState(null)
  const [risk, setRisk] = useState(null)
  const [plan, setPlan] = useState(null)
  const [sum, setSum] = useState(null)
  const [showFacts, setShowFacts] = useState(false)
  const [edit, setEdit] = useState(null)
  const [consent, setConsent] = useState(null)
  const [goalForm, setGoalForm] = useState({ name: '', target: '', days: 180, priority: 2 })
  const [goalNote, setGoalNote] = useState('')
  const timer = useRef(null)
  const H = { role, user }

  useEffect(() => {
    api(`/households/${hid}/forecast`, H).then(setFc).catch(() => setFc(null))
    const loadSummary = (r) => {
      const type = state.pending ? 'plan' : r?.available && r.severity !== 'green' ? 'warning' : 'progress'
      api(`/households/${hid}/summary?type=${type}&lang=${lang}`, H).then(setSum).catch(() => setSum(null))
    }
    api(`/households/${hid}/shortfall`, H).then((r) => { setRisk(r); loadSummary(r) }).catch(() => { setRisk(null); loadSummary(null) })
    api(`/households/${hid}/plan`, H).then((p) => { setPlan(p); setEdit(null) }).catch(() => setPlan(null))
    api(`/households/${hid}/consent`, H).then(setConsent).catch(() => {})
    // eslint-disable-next-line
  }, [hid, tick, lang])

  const pending = state.pending
  const f = fc?.forecast

  const startEdit = (opt) => setEdit({ needs: opt.needs, savings: opt.savings, goalsTotal: opt.goals_total, base: opt, risk: opt.shortfall_prob })
  const changeEdit = (patch) => {
    const e = { ...edit, ...patch }
    const gs = e.base.goals
    const gsum = Object.values(gs).reduce((a, b) => a + b, 0) || 1
    const goals = Object.fromEntries(Object.entries(gs).map(([k, v]) => [k, (v / gsum) * e.goalsTotal]))
    setEdit(e)
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      try {
        const r = await api(`/households/${hid}/plan/evaluate`, { ...H, method: 'POST', body: { needs: e.needs, savings: e.savings, goals } })
        setEdit((cur) => cur && { ...cur, risk: r.shortfall_prob, needs: r.needs, savings: r.savings, goalsTotal: r.goals_total, goalsObj: r.goals })
      } catch { /* ignore */ }
    }, 250)
  }
  const decide = (decision, planObj) =>
    act(() => api(`/households/${hid}/plan/decision`, { ...H, method: 'POST', body: { decision, plan: planObj } }))

  const setScope = (scope, on) =>
    act(() => api(`/households/${hid}/consent`, { ...H, method: 'POST', body: { scope, state: on ? 'granted' : 'revoked' } }))

  const addGoal = async (e) => {
    e.preventDefault()
    setGoalNote('')
    await act(async () => {
      const r = await api(`/households/${hid}/goals`, { ...H, method: 'POST', body: { name: goalForm.name, target: +goalForm.target, days: +goalForm.days, priority: +goalForm.priority } })
      setGoalNote(r.feasible ? `Needs about ${taka(r.per_transfer_needed)} per transfer.` : r.note)
      setGoalForm({ name: '', target: '', days: 180, priority: 2 })
    })
  }

  return (
    <div className="grid">
      <section className="card span2">
        <div className="stats">
          <Stat label={t.moneyInHand} value={taka(state.spendable)} />
          <Stat label={t.buffer} value={taka(state.buffer)} />
          <Stat label={t.goals} value={taka(state.goals_total)} />
          <Stat label="Shortfall days so far" value={state.shortfall_days} warn={state.shortfall_days > 0} />
        </div>
        {state.history.length < 2 && <p className="small muted">The balance chart appears after a few simulated days. Use “Next day” or “+7 days”.</p>}
        <div style={{ height: 150 }}>
          <ResponsiveContainer>
            <AreaChart data={state.history}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} minTickGap={30} />
              <YAxis fontSize={11} width={48} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
              <Tooltip formatter={(v) => taka(v)} labelFormatter={fmtDate} />
              <Area type="monotone" dataKey="balance" name="Money + buffer" stroke="var(--accent)" fill="var(--accent-soft)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {pending && plan?.options?.length > 0 && (
        <section className="card span2 highlight">
          <h2>💸 {t.arrived}: {taka(pending.amount)} <small>{fmtDate(pending.date)}</small></h2>
          <p className="muted">{t.decisionYours} Each option shows the chance of running short before the next transfer.</p>
          <div className="options">
            {plan.options.map((o) => (
              <div className="opt" key={o.style}>
                <h3>{o.label}</h3>
                <Bar parts={[['needs', o.needs], ['savings', o.savings], ['goals', o.goals_total]]} total={o.amount} />
                <ul className="split">
                  <li><i className="d needs" />{t.needs} <b>{taka(o.needs)}</b></li>
                  <li><i className="d savings" />{t.savings} <b>{taka(o.savings)}</b></li>
                  <li><i className="d goals" />{t.goals} <b>{taka(o.goals_total)}</b></li>
                </ul>
                {Object.keys(o.goals).length > 0 && <small className="muted">{Object.entries(o.goals).map(([k, v]) => `${k} ${taka(v)}`).join(' · ')}</small>}
                <div className={`risk ${o.shortfall_prob > 0.5 ? 'red' : o.shortfall_prob > 0.25 ? 'amber' : 'green'}`}>{t.riskLabel}: <b>{pct(o.shortfall_prob)}</b></div>
                <details><summary>Why?</summary><ul className="why">{o.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></details>
                <div className="row">
                  <button className="primary" onClick={() => decide('accept', o)}>{t.accept}</button>
                  <button className="ghost" onClick={() => startEdit(o)}>Adjust</button>
                </div>
              </div>
            ))}
          </div>
          {edit && (
            <div className="edit">
              <h3>Adjust the split <small>(you control this)</small></h3>
              <Slider label={t.needs} max={pending.got} value={edit.needs} onChange={(v) => changeEdit({ needs: v })} />
              <Slider label={t.savings} max={pending.got} value={edit.savings} onChange={(v) => changeEdit({ savings: v })} />
              <Slider label={t.goals} max={pending.got} value={edit.goalsTotal} onChange={(v) => changeEdit({ goalsTotal: v })} />
              <p>Unallocated money stays with you as spendable. {t.riskLabel}: <b>{pct(edit.risk ?? 0)}</b></p>
              <div className="row">
                <button className="primary" onClick={() => {
                  const gs = edit.goalsObj || Object.fromEntries(Object.entries(edit.base.goals).map(([k, v]) => [k, (v / (edit.base.goals_total || 1)) * edit.goalsTotal]))
                  decide('edit', { needs: edit.needs, savings: edit.savings, goals: gs })
                }}>{t.saveEdit}</button>
                <button className="ghost" onClick={() => setEdit(null)}>Cancel</button>
              </div>
            </div>
          )}
          <button className="link" onClick={() => decide('skip', null)}>{t.skip}</button>
        </section>
      )}

      <section className="card">
        <h2>🔮 {t.nextTransfer}</h2>
        {f ? (<>
          <p className="big">{fmtDate(f.next_date_p10)} – {fmtDate(f.next_date_p90)}</p>
          <p className="muted">Most likely around <b>{fmtDate(f.next_date_p50)}</b> · confidence: {fc.confidence_label}{f.overdue && ' · overdue, range widened'}</p>
          <p>{t.amount}: <b>{taka(f.amt_p10)} – {taka(f.amt_p90)}</b> <small className="muted">(typical {taka(f.amt_p50)})</small></p>
          {f.naive && <p className="small muted">A simple “same as last time” guess would say {f.naive.gap} days and {taka(f.naive.amt)}. This is a range, not a promise.</p>}
          {state.sender_intent && <p className="small">Your sender shared a planned transfer; the range reflects it.</p>}
          {fc.drivers?.length > 0 && <details><summary>What shapes this forecast</summary><ul className="why">{fc.drivers.map((d, i) => <li key={i}>{d.feature.replace(/_/g, ' ')} = {Math.round(d.value * 10) / 10} → {d.effect_days > 0 ? '+' : ''}{d.effect_days.toFixed(1)} days</li>)}</ul></details>}
        </>) : <p className="muted">Collecting more history…</p>}
      </section>

      <section className={`card ${risk?.severity || ''}`}>
        <h2>⚠️ {t.warning}</h2>
        {risk?.available ? (<>
          <p className={`badge ${risk.severity}`}>{SEV[risk.severity]}</p>
          <p>{t.riskLabel}: <b>{pct(risk.prob)}</b>{risk.runout_p50 && <> · money may run out in about <b>{Math.round(risk.runout_p50)}</b> days</>}</p>
          {risk.drivers.length > 0 && <ul className="why">{risk.drivers.map((d, i) => <li key={i}>{d.detail}</li>)}</ul>}
          {risk.suggestions.length > 0 && <div className="tips"><b>You could:</b><ul>{risk.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ul></div>}
          <p className="small muted">An estimate from {1000} simulated futures, not a certainty. You decide what to do.</p>
        </>) : <p className="muted">Not enough history yet.</p>}
      </section>

      <section className="card span2">
        <h2>🗣 {t.explanation}</h2>
        {sum ? (<>
          <p className="said">{sum.text}</p>
          <small className="tag">{sum.label} · {sum.source}</small>{' '}
          <button className="link" onClick={() => setShowFacts(!showFacts)}>{showFacts ? 'Hide' : 'Show'} the facts used</button>
          {showFacts && <pre>{JSON.stringify(sum.source_facts, null, 1)}</pre>}
        </>) : <p className="muted">–</p>}
      </section>

      <section className="card">
        <h2>🎯 {t.goals}</h2>
        {state.goals.map((g) => (
          <div key={g.id} className="goal">
            <div className="row between"><b>{g.name}</b><span>{taka(g.current)} / {taka(g.target)}</span></div>
            <div className="progress"><div style={{ width: `${g.pct}%` }} /></div>
          </div>
        ))}
        <form className="addgoal" onSubmit={addGoal}>
          <input placeholder="New goal (e.g. Education)" value={goalForm.name} onChange={(e) => setGoalForm({ ...goalForm, name: e.target.value })} required maxLength={40} />
          <input type="number" placeholder="Target ৳" value={goalForm.target} onChange={(e) => setGoalForm({ ...goalForm, target: e.target.value })} required min="1" />
          <input type="number" title="Days to deadline" value={goalForm.days} onChange={(e) => setGoalForm({ ...goalForm, days: e.target.value })} min="14" />
          <button className="ghost">{t.addGoal}</button>
        </form>
        {goalNote && <p className="small muted">{goalNote}</p>}
      </section>

      <section className="card">
        <h2>🤝 {t.sharing}</h2>
        <p className="muted small">Your sender sees goal progress only, never your transactions, unless you choose to share more. You can change this any time.</p>
        {consent && (<>
          <p className="small">Sender link: {consent.sender_accepted ? 'accepted ✓' : 'waiting for the sender to accept'}</p>
          {[['goal_progress', 'Goal progress'], ['savings_total', 'Total savings'], ['spending_categories', 'Spending categories (not available in this demo)']].map(([k, label]) => (
            <label key={k} className="toggle">
              <input type="checkbox" disabled={k === 'spending_categories'} checked={consent.scopes[k] === 'granted'} onChange={(e) => setScope(k, e.target.checked)} />
              <span>{label}{consent.scopes[k] === 'requested' && <em> · sender asked to see this</em>}</span>
            </label>
          ))}
        </>)}
      </section>
    </div>
  )
}

const Stat = ({ label, value, warn }) => <div className={`stat ${warn ? 'warn' : ''}`}><small>{label}</small><b>{value}</b></div>
const Bar = ({ parts, total }) => (
  <div className="stack">{parts.map(([k, v]) => <div key={k} className={k} style={{ width: `${(v / total) * 100}%` }} />)}</div>
)
const Slider = ({ label, value, max, onChange }) => (
  <label className="slider"><span>{label}: <b>{taka(value)}</b></span>
    <input type="range" min="0" max={Math.round(max)} step="100" value={Math.round(value)} onChange={(e) => onChange(+e.target.value)} /></label>
)
