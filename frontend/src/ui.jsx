import { useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtDate, taka } from './api'

const ICONS = {
  home: 'M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  payments: 'M3 6h18v12H3zM3 10h18',
  plan: 'M4 20V4M4 20h16M8 15l4-4 3 3 5-6',
  goals: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 11a1 1 0 1 0 0 2 1 1 0 0 0 0-2z',
  insights: 'M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z',
  check: 'M5 12l5 5 9-10',
}
export const Icon = ({ name, size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={ICONS[name]} /></svg>
)

export function Modal({ title, onClose, children, wide }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet" style={wide ? { maxWidth: 640 } : undefined} onClick={(e) => e.stopPropagation()}>
        <div className="head"><h2 style={{ fontSize: 18 }}>{title}</h2><button className="link gray" onClick={onClose}>Close</button></div>
        {children}
      </div>
    </div>
  )
}

/** Purple badge. With `why`, a "Why?" link opens an explanation (separates predictions from facts). */
export function AI({ label = 'AI estimate', title = 'Why this estimate?', why, tone }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <span className={`ai ${tone || ''}`}>{label}{why && <button className="link" onClick={() => setOpen(true)}>Why?</button>}</span>
      {open && <Modal title={title} onClose={() => setOpen(false)}>{why}</Modal>}
    </>
  )
}

export const Bar = ({ pct, tone = '' }) => <div className={`bar ${tone}`}><div style={{ width: `${Math.max(0, Math.min(pct, 100))}%` }} /></div>
export const Toggle = ({ checked, onChange, label }) => (
  <label className="row" style={{ gap: 10 }}>{label && <span className="grow small">{label}</span>}<span className="toggle"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} /><i /></span></label>
)
export const Avatar = ({ text }) => <span className="avatar">{(text || '?')[0].toUpperCase()}</span>

export const STATUS = { scheduled: ['Scheduled', 'green'], paid: ['Paid', 'blue'], needs_review: ['Needs review', 'red'], at_risk: ['At risk', 'amber'], overdue: ['Overdue', 'red'] }
export const Chip = ({ status }) => { const [t, c] = STATUS[status] || [status, 'gray']; return <span className={`chip ${c}`}>{t}</span> }
export const DOT = { scheduled: 'green', paid: 'blue', needs_review: 'red', at_risk: 'amber', overdue: 'red' }

export const Slider = ({ label, value, max, onChange }) => (
  <label className="slider"><span className="small">{label}: <b>{taka(value)}</b></span>
    <input type="range" min="0" max={Math.round(max)} step="100" value={Math.round(value)} onChange={(e) => onChange(+e.target.value)} /></label>
)

/** Projected balance with an uncertainty band; red where the middle path is below zero. */
export function Projection({ pj, height = 230 }) {
  if (!pj) return <p className="muted">Available once a forecast exists.</p>
  const rows = [{ date: 'today', band: [pj.starting_balance, pj.starting_balance], pos: pj.starting_balance, neg: null }].concat(
    pj.days.map((d, i) => ({ date: pj.dates[i], band: [pj.p10[i], pj.p90[i]], pos: pj.p50[i] >= 0 ? pj.p50[i] : null, neg: pj.p50[i] < 0 ? pj.p50[i] : null })))
  const firstNeg = pj.p50.findIndex((v) => v < 0)
  const ticks = [rows[0].date, rows[Math.floor(rows.length / 3)].date, rows[Math.floor((2 * rows.length) / 3)].date, rows[rows.length - 1].date]
  return (
    <>
      <div style={{ height }}>
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ left: 0, right: 6, top: 8 }}>
            <CartesianGrid vertical={false} stroke="#eef2f6" />
            <XAxis dataKey="date" ticks={ticks} tickFormatter={(v, i) => (i === 0 ? 'Today' : i === 3 ? 'Next transfer' : fmtDate(v))} fontSize={12} tickLine={false} axisLine={false} />
            <YAxis fontSize={11} width={40} tickLine={false} axisLine={false} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
            <Tooltip formatter={(v) => (Array.isArray(v) ? `${taka(v[0])} to ${taka(v[1])}` : taka(v))} labelFormatter={(l) => (l === 'today' ? 'Today' : fmtDate(l))} />
            <ReferenceLine y={0} stroke="#d14343" strokeDasharray="4 3" />
            <Area isAnimationActive={false} dataKey="band" name="Forecast range" stroke="none" fill="#0e6e9c" fillOpacity={0.12} />
            <Line isAnimationActive={false} dataKey="pos" name="Most likely" stroke="#0e6e9c" dot={false} strokeWidth={2.5} connectNulls={false} />
            <Line isAnimationActive={false} dataKey="neg" name="Below zero" stroke="#d14343" dot={false} strokeWidth={3} connectNulls={false} />
            {pj.bills.map((b, i) => <ReferenceDot key={i} x={pj.dates[b.day - 1]} y={pj.p50[b.day - 1]} r={5} fill="#0f2a44" stroke="#fff" strokeWidth={1.5} />)}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="tiny muted">● Dots = EMI and bill payments · Red dashed line = zero balance · Shaded = forecast range</p>
      {firstNeg >= 0
        ? <p className="small txt-red" style={{ fontWeight: 600, marginTop: 6 }}>Balance may drop below zero around {fmtDate(pj.dates[firstNeg])}{pj.next_p90 > firstNeg + 1 ? ' if the transfer comes late.' : '.'}</p>
        : <p className="small txt-green" style={{ fontWeight: 600, marginTop: 6 }}>Balance is expected to stay above zero until your next transfer.</p>}
    </>
  )
}

export const CAT = { food: ['Food & groceries', '#0e6e9c'], bills: ['Bills & EMI', '#6a4bd8'], education: ['Education', '#1e9e63'], transport: ['Transport', '#c27c00'], health: ['Health', '#d14343'], other: ['Other', '#9aa6b2'] }
export const FEATURE = {
  gap_mean_all: 'Usual gap between transfers', gap_mean3: 'Recent gap between transfers', last_gap: 'Last gap between transfers',
  gap_std_all: 'How much the gap varies', gap_cv: 'How much the gap varies', late_rate: 'Past transfers that were late',
  days_to_eid: 'Eid timing', eid_within_30: 'Eid within a month', last_amt: 'Latest transfer amount', amt_mean3: 'Recent transfer amounts',
  amt_mean_all: 'Usual transfer amount', amt_cv: 'How much amounts vary', dom: 'Day of the month', month: 'Time of year', n_events: 'Length of history',
  local_income_monthly: 'Local income', size: 'Household size', is_rural: 'Rural or urban',
}
