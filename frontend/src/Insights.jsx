import { useEffect, useState } from 'react'
import { Bar as RBar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { api, monthName, pct, taka } from './api'
import { AI, FEATURE } from './ui'

export default function Insights({ hid, state, tick, lang, H }) {
  const [d, setD] = useState(null)
  const [sum, setSum] = useState(null)
  const [hist, setHist] = useState(null)
  const [facts, setFacts] = useState(false)
  useEffect(() => {
    api(`/households/${hid}/insights`, H).then(setD).catch(() => setD(null))
    api(`/households/${hid}/summary?type=monthly&lang=${lang}`, H).then(setSum).catch(() => setSum(null))
    api(`/households/${hid}/bills/history`, H).then(setHist).catch(() => setHist(null))
    // eslint-disable-next-line
  }, [hid, tick, lang])
  if (!d) return <p className="muted">Loading…</p>

  const months = (state.buffer / Math.max(state.monthly_needs + (state.bills_monthly || 0), 1)).toFixed(1)
  const fd = [...d.forecast_drivers].sort((a, b) => Math.abs(b.effect_days) - Math.abs(a.effect_days)).slice(0, 4)
  const maxF = Math.max(...fd.map((x) => Math.abs(x.effect_days)), 0.1)
  const download = () => {
    const txt = [`RemitWise report · ${monthName(state.date)}`, `On-time payments: ${d.on_time_rate == null ? 'n/a' : pct(d.on_time_rate)} (${state.bills_on_time} of ${d.bills_due})`, `Late fees avoided: ${taka(d.late_fees_avoided)}`, `Savings built: ${taka(d.savings_built)}`, `Unusual bills caught: ${d.anomalies_caught}`, '', sum?.text || '', '', 'All amounts are calculated in code; the AI only explains them. Synthetic data.'].join('\n')
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([txt], { type: 'text/plain' })); a.download = 'remitwise-report.txt'; a.click()
  }

  return (
    <div className="stackv">
      <div className="pagehead"><div><h1>Insights</h1><p>{monthName(state.date)} summary</p></div><button className="btn only-desktop" onClick={download}>Download report</button></div>

      <div className="grid4 tiles">
        <section className="card tile"><small>Late fees avoided</small><b className="txt-green">{taka(d.late_fees_avoided)}</b><span className="foot">so far</span></section>
        <section className="card tile"><small>On-time payments</small><b className="txt-blue">{d.on_time_rate == null ? '–' : pct(d.on_time_rate)}</b><span className="foot">{state.bills_on_time} of {d.bills_due}</span></section>
        <section className="card tile"><small>Emergency buffer</small><b className="txt-amber">{months} mo</b><span className="foot">target 1 month of needs</span></section>
        <section className="card tile"><small>Kept in wallet</small><b className="txt-purple">{state.retained_share == null ? '–' : pct(state.retained_share)}</b><span className="foot">beyond 24 hours</span></section>
      </div>

      <div className="grid2e" style={{ gridTemplateColumns: '1.1fr 1fr' }}>
        <section className="card purple" style={{ alignSelf: 'start' }}>
          <span className="ai" style={{ background: 'transparent', padding: 0 }}>AI summary</span>
          {sum ? (<>
            <p style={{ margin: '8px 0', fontSize: 15 }}>{sum.text}</p>
            <p className="tiny muted">Generated from computed numbers only. Predictions are marked as estimates.</p>
            <span className="tag">{sum.label} · {sum.source}</span> <button className="link" onClick={() => setFacts(!facts)}>{facts ? 'Hide' : 'Show'} the facts used</button>
            {facts && <pre>{JSON.stringify(sum.source_facts, null, 1)}</pre>}
          </>) : <p className="muted">–</p>}
        </section>
        <div className="stackv">
          <section className="card">
            <div className="row between"><h2>Why the next transfer looks like this</h2><AI label="Explanation" title="How to read this" why={<p>Each bar shows how much one factor moved the predicted wait for your next transfer, from the model's feature contributions. “Later” means it adds days; “earlier” means it saves days.</p>} /></div>
            {fd.map((x, i) => (
              <div className="barrow" key={i}>
                <div className="row between small"><span>{FEATURE[x.feature] || x.feature.replace(/_/g, ' ')}</span><span className="muted">{x.effect_days > 0 ? `adds ~${x.effect_days.toFixed(1)} days` : `saves ~${Math.abs(x.effect_days).toFixed(1)} days`}</span></div>
                <div className="hbar"><div style={{ width: `${(Math.abs(x.effect_days) / maxF) * 100}%`, background: x.effect_days > 0 ? 'var(--amber)' : 'var(--green)' }} /></div>
              </div>
            ))}
            {!fd.length && <p className="muted small">–</p>}
          </section>
          {d.warning_drivers.length > 0 && (
            <section className="card">
              <div className="row between"><h2>Why we expect a shortfall</h2><AI label="Top reasons" why={<p>These are the reasons the early-warning check found. A bigger bar means a bigger effect.</p>} /></div>
              {d.warning_drivers.map((x, i) => (
                <div className="barrow" key={i}><div className="row between small"><span>{x.detail}</span><b className="txt-red">{Math.round(x.magnitude * 100)}%</b></div><div className="hbar"><div style={{ width: `${x.magnitude * 100}%`, background: 'var(--red)' }} /></div></div>
              ))}
            </section>
          )}
        </div>
      </div>

      {hist && (
        <section className="card">
          <div className="row between"><h2>{hist.name} bill: last {hist.points.length - 1} months and next month</h2><AI label={`AI estimate for ${hist.points[hist.points.length - 1].label}`} why={<p>The estimate for the next bill uses the same month last year. On our synthetic data this is about 10% off on average, versus about 16% for “same as last month”.</p>} /></div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer>
              <BarChart data={hist.points} margin={{ top: 22 }}>
                <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis hide domain={[0, 'dataMax + 300']} />
                <RBar dataKey="amount" radius={[8, 8, 0, 0]} isAnimationActive={false}>
                  {hist.points.map((p, i) => <Cell key={i} fill={p.estimate ? '#dcd3fb' : '#0e6e9c'} stroke={p.estimate ? '#6a4bd8' : 'none'} strokeDasharray={p.estimate ? '5 4' : undefined} />)}
                  <LabelList dataKey="amount" position="top" formatter={(v) => taka(v)} fontSize={11} />
                </RBar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
      <p className="tiny muted">AI values are estimates. All amounts are calculated in code; the AI only explains them.</p>
    </div>
  )
}
