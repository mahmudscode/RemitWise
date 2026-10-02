import { useEffect, useRef, useState } from 'react'
import { api, taka } from './api'
import { Modal, Slider, Stack } from './ui'

export default function RemittanceModal({ hid, state, person, H, act, onClose }) {
  const [plan, setPlan] = useState(null)
  const [idx, setIdx] = useState(1)
  const [edit, setEdit] = useState(null)
  const [risk, setRisk] = useState(null)
  const timer = useRef(null)
  const p = state.pending

  useEffect(() => { api(`/households/${hid}/plan`, H).then((r) => { setPlan(r); setRisk(null); setEdit(null) }).catch(() => setPlan(null)) /* eslint-disable-next-line */ }, [hid, p?.seq])
  if (!plan?.options?.length) return null
  const o = plan.options[idx]
  const cur = edit || { bills: o.bills, needs: o.needs, savings: o.savings, goals: o.goals_total }

  const change = (patch) => {
    const e = { ...cur, ...patch }
    setEdit(e)
    const gsum = Object.values(o.goals).reduce((a, b) => a + b, 0) || 1
    const goals = Object.fromEntries(Object.entries(o.goals).map(([k, v]) => [k, (v / gsum) * e.goals]))
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      try { const r = await api(`/households/${hid}/plan/evaluate`, { ...H, method: 'POST', body: { needs: e.needs, savings: e.savings, bills: e.bills, goals } }); setRisk(r.shortfall_prob) } catch { /* ignore */ }
    }, 250)
  }
  const goalsObj = () => {
    const gsum = Object.values(o.goals).reduce((a, b) => a + b, 0) || 1
    return Object.fromEntries(Object.entries(o.goals).map(([k, v]) => [k, (v / gsum) * cur.goals]))
  }
  const send = (decision, planObj) => act(() => api(`/households/${hid}/plan/decision`, { ...H, method: 'POST', body: { decision, plan: planObj } })).then(onClose)
  const shown = risk ?? o.shortfall_prob

  return (
    <Modal title="Remittance arrived" onClose={onClose}>
      <p className="big">{taka(p.amount)} <small>received from {person?.sender_name} ({person?.sender_city})</small></p>
      <div className="chips">{plan.options.map((x, i) => <button key={x.style} className={i === idx ? 'chip2 on' : 'chip2'} onClick={() => { setIdx(i); setEdit(null); setRisk(null) }}>{x.label}</button>)}</div>
      <Stack parts={[['bills', cur.bills], ['needs', cur.needs], ['savings', cur.savings], ['goals', cur.goals]]} total={p.got} />
      <ul className="split">
        <li><span><i className="d bills" />Bills and EMI</span><b>{taka(cur.bills)}</b></li>
        <li><span><i className="d needs" />Daily needs</span><b>{taka(cur.needs)}</b></li>
        <li><span><i className="d savings" />Emergency fund</span><b>{taka(cur.savings)}</b></li>
        <li><span><i className="d goals" />Goals{Object.keys(o.goals).length > 0 && <small> ({Object.keys(o.goals).join(', ')})</small>}</span><b>{taka(cur.goals)}</b></li>
      </ul>
      <div className={`risk ${shown > 0.5 ? 'red' : shown > 0.25 ? 'amber' : 'green'}`}>Chance of running short: <b>{Math.round(shown * 100)}%</b> <small>(AI estimate)</small></div>
      <details><summary>Why this split?</summary><ul className="why">{o.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></details>
      {edit && (<div className="edit">
        <Slider label="Bills and EMI" max={p.got} value={cur.bills} onChange={(v) => change({ bills: v })} />
        <Slider label="Daily needs" max={p.got} value={cur.needs} onChange={(v) => change({ needs: v })} />
        <Slider label="Emergency fund" max={p.got} value={cur.savings} onChange={(v) => change({ savings: v })} />
        <Slider label="Goals" max={p.got} value={cur.goals} onChange={(v) => change({ goals: v })} />
        <p className="small muted">Anything not assigned stays with you as spendable money.</p>
      </div>)}
      <p className="small muted">These are suggestions. The decision is yours.</p>
      <div className="row wrap">
        {edit ? <button className="primary" onClick={() => send('edit', { ...cur, goals: goalsObj() })}>Use my edit</button>
          : <button className="primary" onClick={() => send('accept', o)}>Accept plan</button>}
        <button onClick={() => (edit ? setEdit(null) : change({}))}>{edit ? 'Cancel edit' : 'Adjust'}</button>
        <button className="link" onClick={() => send('skip', null)}>Skip for now</button>
      </div>
    </Modal>
  )
}
