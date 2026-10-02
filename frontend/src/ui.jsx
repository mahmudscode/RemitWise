import { useState } from 'react'

export function Modal({ title, onClose, children }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="row between"><h3>{title}</h3><button className="link" onClick={onClose}>Close</button></div>
        {children}
      </div>
    </div>
  )
}

/** Small "AI estimate" badge with a "Why?" link. Separates predictions from facts (transparency rule). */
export function AI({ label = 'AI estimate', title = 'Why this estimate?', why }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <span className="ai"><b>{label}</b>{why && <> · <button className="link" onClick={() => setOpen(true)}>Why?</button></>}</span>
      {open && <Modal title={title} onClose={() => setOpen(false)}>{why}</Modal>}
    </>
  )
}

export const Progress = ({ pct }) => <div className="progress"><div style={{ width: `${Math.min(pct, 100)}%` }} /></div>

export const Stack = ({ parts, total }) => (
  <div className="stack">{parts.map(([k, v]) => <div key={k} className={k} style={{ width: `${total ? (v / total) * 100 : 0}%` }} />)}</div>
)

export const Slider = ({ label, value, max, onChange }) => (
  <label className="slider"><span>{label}: <b>৳{Math.round(value).toLocaleString('en-US')}</b></span>
    <input type="range" min="0" max={Math.round(max)} step="100" value={Math.round(value)} onChange={(e) => onChange(+e.target.value)} /></label>
)

export const STATUS = {
  scheduled: ['Scheduled', 'blue'], paid: ['Paid', 'green'], needs_review: ['Needs review', 'amber'],
  at_risk: ['At risk', 'amber'], overdue: ['Overdue', 'red'],
}
export const Chip = ({ status }) => { const [t, c] = STATUS[status] || [status, 'blue']; return <span className={`chip ${c}`}>{t}</span> }
export const KIND_ICON = { utility: '💡', emi: '🏍️', school: '🎓', other: '🧾' }
