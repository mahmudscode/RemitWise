import { useEffect, useRef, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { Icon, Modal, Slider } from './ui'
import { t, tb } from './i18n'

export default function RemittanceModal({ hid, state, person, H, act, onClose }) {
  const [plan, setPlan] = useState(null)
  const [bills, setBills] = useState([])
  const [idx, setIdx] = useState(1)
  const [edit, setEdit] = useState(null)
  const [risk, setRisk] = useState(null)
  const timer = useRef(null)
  const p = state.pending

  useEffect(() => {
    api(`/households/${hid}/plan`, H).then((r) => { setPlan(r); setRisk(null); setEdit(null) }).catch(() => setPlan(null))
    api(`/households/${hid}/bills`, H).then((r) => setBills(r.items)).catch(() => {})
    // eslint-disable-next-line
  }, [hid, p?.seq])
  if (!plan?.options?.length) return null
  const o = plan.options[idx]
  const f = plan.forecast
  const cur = edit || { bills: o.bills, needs: o.needs, savings: o.savings, goals: o.goals_total }
  const dueSoon = bills.filter((b) => ['scheduled', 'at_risk'].includes(b.display_status) && b.due_day <= state.day + f.gap_p50)
  const nEmi = dueSoon.filter((b) => b.kind === 'emi').length
  const nBills = dueSoon.length - nEmi
  const dailyNet = Math.max(state.daily_needs, 1)
  const gsum = Object.values(o.goals).reduce((a, b) => a + b, 0) || 1
  const goalsOf = (total) => Object.fromEntries(Object.entries(o.goals).map(([k, v]) => [k, (v / gsum) * total]))

  const change = (patch) => {
    const e = { ...cur, ...patch }
    setEdit(e)
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      try { const r = await api(`/households/${hid}/plan/evaluate`, { ...H, method: 'POST', body: { needs: e.needs, savings: e.savings, bills: e.bills, goals: goalsOf(e.goals) } }); setRisk(r.shortfall_prob) } catch { /* ignore */ }
    }, 250)
  }
  const send = (decision, planObj) => act(() => api(`/households/${hid}/plan/decision`, { ...H, method: 'POST', body: { decision, plan: planObj } })).then(onClose).catch(() => {})
  const shown = risk ?? o.shortfall_prob
  const parts = [['c-bills', cur.bills], ['c-needs', cur.needs], ['c-savings', cur.savings], ['c-goals', cur.goals]]
  const months = (state.buffer + (edit ? cur.savings : o.savings)) / Math.max(state.monthly_needs + (state.bills_monthly || 0), 1)
  const goalRows = Object.entries(o.goals)
  const goalInfo = Object.fromEntries(state.goals.map((g) => [g.name, g]))

  return (
    <Modal title="" onClose={onClose}>
      <div style={{ textAlign: 'center' }}>
        <div className="check-ico"><Icon name="check" size={28} /></div>
        <p className="muted">{t('Money received')}</p>
        <p style={{ fontSize: 40, fontWeight: 800, lineHeight: 1.1 }}>{taka(p.amount)}</p>
        <p className="muted small">{t('from {who} · {city} · {d}', { who: person?.sender_name, city: person?.sender_city, d: fmtDate(p.date) })}</p>
      </div>
      <div className="card" style={{ marginTop: 14, padding: '14px 16px' }}>
        <div className="row between"><h2>{t('Suggested split')}</h2><span className="ai">{t('AI plan')}</span></div>
        <div className="seg" style={{ margin: '8px 0' }}>{plan.options.map((x, i) => <button key={x.style} className={i === idx ? 'on' : ''} onClick={() => { setIdx(i); setEdit(null); setRisk(null) }}>{tb(x.label)}</button>)}</div>
        <div className="stack">{parts.map(([c, v]) => <div key={c} className={c} style={{ width: `${(v / p.got) * 100}%` }} />)}</div>
        <Row color="var(--primary)" title={t('Bills & EMI')} sub={t('Reserved first')} value={cur.bills} />
        <Row color="var(--green)" title={t('Daily needs')} sub={t('Covers ~{n} days', { n: Math.round(cur.needs / dailyNet) })} value={cur.needs} />
        <Row color="var(--amber)" title={t('Emergency fund')} sub={t('Now {n} months saved', { n: months.toFixed(1) })} value={cur.savings} />
        {goalRows.length === 0 && <Row color="var(--purple)" title={t('Goals')} sub={t('Nothing this time')} value={cur.goals} />}
        {goalRows.map(([name, amt]) => <Row key={name} color="var(--purple)" title={t('Goal: {name}', { name: tb(name) })} sub={goalInfo[name] ? t('{n}% of target', { n: Math.round(goalInfo[name].pct) }) : ''} value={edit ? (amt / gsum) * cur.goals : amt} />)}
      </div>
      <div className="card info" style={{ marginTop: 12, padding: '12px 14px', fontSize: 14 }}>
        {t('Based on your next transfer expected in {a}–{b} days, {bills}{emi} due before then. You can adjust any amount.', { a: Math.round(f.gap_p10), b: Math.round(f.gap_p90), bills: t(nBills === 1 ? '{n} bill' : '{n} bills', { n: nBills }), emi: nEmi ? t(' and {n} EMI', { n: nEmi }) : '' })}
        <div className="small" style={{ marginTop: 6 }}>{t('Chance of running short with this split:')} <b>{Math.round(shown * 100)}%</b> <span className="ai" style={{ marginLeft: 4 }}>{t('AI estimate')}</span></div>
      </div>
      <details style={{ marginTop: 8 }}><summary>{t('Why this split?')}</summary><ul className="why">{o.reasons.map((r, i) => <li key={i}>{tb(r)}</li>)}</ul></details>
      {edit && <div style={{ marginTop: 10 }}>
        <Slider label={t('Bills & EMI')} max={p.got} value={cur.bills} onChange={(v) => change({ bills: v })} />
        <Slider label={t('Daily needs')} max={p.got} value={cur.needs} onChange={(v) => change({ needs: v })} />
        <Slider label={t('Emergency fund')} max={p.got} value={cur.savings} onChange={(v) => change({ savings: v })} />
        <Slider label={t('Goals')} max={p.got} value={cur.goals} onChange={(v) => change({ goals: v })} />
        <p className="tiny muted">{t('Anything not assigned stays with you as spendable money.')}</p>
      </div>}
      <p className="tiny muted" style={{ margin: '10px 0' }}>{t('These are suggestions. The decision is yours.')}</p>
      <div className="stackv" style={{ gap: 8 }}>
        {edit ? <button className="btn primary block" onClick={() => send('edit', { ...cur, goals: goalsOf(cur.goals) })}>{t('Use my amounts')}</button>
          : <button className="btn primary block" onClick={() => send('accept', o)}>{t('Accept plan')}</button>}
        <button className="btn block" onClick={() => (edit ? setEdit(null) : change({}))}>{edit ? t('Cancel adjusting') : t('Adjust amounts')}</button>
        <button className="link gray" onClick={() => send('skip', null)}>{t('Skip for now')}</button>
      </div>
    </Modal>
  )
}
const Row = ({ color, title, sub, value }) => (
  <div className="split-row"><span className="dotc" style={{ background: color }} /><div className="grow"><b style={{ fontWeight: 600 }}>{title}</b><small>{sub}</small></div><b>{taka(value)}</b></div>
)
