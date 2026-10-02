import { useEffect, useState } from 'react'
import { Area, CartesianGrid, Cell, ComposedChart, Line, Pie, PieChart, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fmtDate, taka } from './api'
import { AI } from './ui'

const CAT_COLOR = { food: '#1f7a5a', transport: '#3b6fd4', education: '#d08a1e', health: '#c2503a', other: '#8a8fa0', bills: '#6b4fbb' }

export default function Plan({ hid, tick, H, act }) {
  const [pj, setPj] = useState(null)
  const [cats, setCats] = useState(null)
  const [opts, setOpts] = useState([])
  const [note, setNote] = useState('')

  useEffect(() => {
    api(`/households/${hid}/plan/projection`, H).then(setPj).catch(() => setPj(null))
    api(`/households/${hid}/plan/categories`, H).then(setCats).catch(() => setCats(null))
    api(`/households/${hid}/plan/options`, H).then((r) => setOpts(r.options)).catch(() => setOpts([]))
    // eslint-disable-next-line
  }, [hid, tick])

  const rows = pj ? pj.days.map((d, i) => ({ date: pj.dates[i], band: [pj.p10[i], pj.p90[i]], pos: pj.p50[i] >= 0 ? pj.p50[i] : null, neg: pj.p50[i] < 0 ? pj.p50[i] : null, p50: pj.p50[i] })) : []
  const dateAt = (off) => pj.dates[Math.min(Math.max(Math.round(off) - 1, 0), pj.dates.length - 1)]

  return (
    <div className="stackv">
      <section className="card">
        <div className="row between"><h2>Cash flow until the next transfer</h2><AI why={<div><p>We simulate hundreds of possible futures for your daily spending and show the middle path and a shaded range (10th to 90th percentile). Bills and EMIs are paid from your bill vault first, and appear as markers.</p><p className="small muted">Where the line dips below zero it turns red: that is when you could run short.</p></div>} /></div>
        {pj ? (<>
          <div style={{ height: 230 }}>
            <ResponsiveContainer>
              <ComposedChart data={rows} margin={{ left: 0, right: 8, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} minTickGap={28} />
                <YAxis fontSize={11} width={44} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                <Tooltip formatter={(v) => (Array.isArray(v) ? `${taka(v[0])} to ${taka(v[1])}` : taka(v))} labelFormatter={fmtDate} />
                <ReferenceArea x1={dateAt(pj.next_p10)} x2={dateAt(pj.next_p90)} fill="var(--accent-soft)" fillOpacity={0.7} label={{ value: 'transfer likely', fontSize: 10, position: 'insideTop' }} />
                <ReferenceLine y={0} stroke="var(--red)" strokeDasharray="4 3" />
                <Area isAnimationActive={false} dataKey="band" name="Likely range" stroke="none" fill="var(--accent)" fillOpacity={0.18} />
                <Line isAnimationActive={false} dataKey="pos" name="Most likely" stroke="var(--accent)" dot={false} strokeWidth={2} connectNulls={false} />
                <Line isAnimationActive={false} dataKey="neg" name="Below zero" stroke="var(--red)" dot={false} strokeWidth={2.5} connectNulls={false} />
                {pj.bills.map((b, i) => <ReferenceDot key={i} x={pj.dates[b.day - 1]} y={pj.p50[b.day - 1]} r={4} fill="#6b4fbb" stroke="none" />)}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="small muted"><i className="dot" style={{ background: '#6b4fbb' }} /> bill or EMI · shaded column: when the next transfer is likely. {pj.goes_negative ? '⚠️ The middle path goes below zero.' : 'The middle path stays above zero.'}</p>
        </>) : <p className="muted">Available once a forecast exists.</p>}
      </section>

      {opts.length > 0 && (
        <section className="card flag">
          <h2>Ways to avoid running short</h2>
          <p className="small muted">You choose. Nothing happens unless you press a button.</p>
          {opts.map((o) => (
            <div className="opt2" key={o.id}>
              <div><b>{o.title}</b><small>{o.detail}</small></div>
              {o.actionable && <button className="primary" onClick={() => act(async () => { await api(`/households/${hid}/plan/options/apply`, { ...H, method: 'POST', body: { option: o.id } }); setNote(o.id === 'ask_sender' ? 'Your sender has been asked.' : 'Moved. You can top the goals up later.') })}>Do this</button>}
            </div>
          ))}
          {note && <p className="small">{note}</p>}
        </section>
      )}

      <section className="card">
        <div className="row between"><h2>Spending by category</h2><AI label="Simulated" title="About these categories" why={<p>Categories are simulated shares of each household's spending (an assumption), plus the bills you actually paid in the last 30 days.</p>} /></div>
        {cats?.items?.length ? (
          <div className="row" style={{ alignItems: 'center' }}>
            <div style={{ width: 150, height: 150 }}>
              <ResponsiveContainer><PieChart><Pie isAnimationActive={false} data={cats.items} dataKey="amount" nameKey="category" innerRadius={38} outerRadius={64} paddingAngle={2}>{cats.items.map((c) => <Cell key={c.category} fill={CAT_COLOR[c.category]} />)}</Pie><Tooltip formatter={(v) => taka(v)} /></PieChart></ResponsiveContainer>
            </div>
            <ul className="legend">{cats.items.map((c) => <li key={c.category}><i className="dot" style={{ background: CAT_COLOR[c.category] }} />{c.category} <b>{taka(c.amount)}</b></li>)}</ul>
          </div>
        ) : <p className="muted">–</p>}
        <p className="small muted">Last 30 days.</p>
      </section>
    </div>
  )
}
