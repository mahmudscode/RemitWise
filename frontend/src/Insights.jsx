import { useEffect, useState } from 'react'
import { Bar as RBar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { api, monthName, pct, taka } from './api'
import { AI, ft } from './ui'
import { t, tb } from './i18n'

export default function Insights({ hid, state, tick, lang, H }) {
  const [d, setD] = useState(null)
  const [sum, setSum] = useState(null)
  const [hist, setHist] = useState(null)
  const [facts, setFacts] = useState(false)
  const [ev, setEv] = useState(null)
  useEffect(() => {
    api(`/households/${hid}/insights`, H).then(setD).catch(() => setD(null))
    api(`/households/${hid}/summary?type=monthly&lang=${lang}`, H).then(setSum).catch(() => setSum(null))
    api(`/households/${hid}/bills/history`, H).then(setHist).catch(() => setHist(null))
    api('/evaluation').then(setEv).catch(() => setEv(null))
    // eslint-disable-next-line
  }, [hid, tick, lang])
  if (!d) return <p className="muted">{t('Loading…')}</p>

  const months = (state.buffer / Math.max(state.monthly_needs + (state.bills_monthly || 0), 1)).toFixed(1)
  const fd = [...d.forecast_drivers].sort((a, b) => Math.abs(b.effect_days) - Math.abs(a.effect_days)).slice(0, 4)
  const maxF = Math.max(...fd.map((x) => Math.abs(x.effect_days)), 0.1)
  const download = () => {
    const txt = [`RemitWise report · ${monthName(state.date)}`, `On-time payments: ${d.on_time_rate == null ? 'n/a' : pct(d.on_time_rate)} (${state.bills_on_time} of ${d.bills_due})`, `Late fees avoided: ${taka(d.late_fees_avoided)}`, `Savings built: ${taka(d.savings_built)}`, `Unusual bills caught: ${d.anomalies_caught}`, '', sum?.text || '', '', 'All amounts are calculated in code; the AI only explains them. Synthetic data.'].join('\n')
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([txt], { type: 'text/plain' })); a.download = 'remitwise-report.txt'; a.click()
  }

  return (
    <div className="stackv">
      <div className="pagehead"><div><h1>{t('Insights')}</h1><p>{t('{m} summary', { m: monthName(state.date) })}</p></div><button className="btn only-desktop" onClick={download}>{t('Download report')}</button></div>

      <div className="grid4 tiles">
        <section className="card tile"><small>{t('Late fees avoided')}</small><b className="txt-green">{taka(d.late_fees_avoided)}</b><span className="foot">{t('so far')}</span></section>
        <section className="card tile"><small>{t('On-time payments')}</small><b className="txt-blue">{d.on_time_rate == null ? '–' : pct(d.on_time_rate)}</b><span className="foot">{t('{a} of {b}', { a: state.bills_on_time, b: d.bills_due })}</span></section>
        <section className="card tile"><small>{t('Emergency buffer')}</small><b className="txt-amber">{months} {t('mo')}</b><span className="foot">{t('target 1 month of needs')}</span></section>
        <section className="card tile"><small>{t('Kept in wallet')}</small><b className="txt-purple">{state.retained_share == null ? '–' : pct(state.retained_share)}</b><span className="foot">{t('beyond 24 hours')}</span></section>
      </div>

      <div className="grid2e" style={{ gridTemplateColumns: '1.1fr 1fr' }}>
        <section className="card purple" style={{ alignSelf: 'start' }}>
          <span className="ai" style={{ background: 'transparent', padding: 0 }}>{t('AI summary')}</span>
          {sum ? (<>
            <p style={{ margin: '8px 0', fontSize: 15 }}>{sum.text}</p>
            <p className="tiny muted">{t('Generated from computed numbers only. Predictions are marked as estimates.')}</p>
            <span className="tag">{tb(sum.label)} · {sum.source}</span> <button className="link" onClick={() => setFacts(!facts)}>{facts ? t('Hide the facts used') : t('Show the facts used')}</button>
            {facts && <pre>{JSON.stringify(sum.source_facts, null, 1)}</pre>}
          </>) : <p className="muted">–</p>}
        </section>
        <div className="stackv">
          <section className="card">
            <div className="row between"><h2>{t('Why the next transfer looks like this')}</h2><AI label="Explanation" title="How to read this" why={<p>{t("Each bar shows how much one factor moved the predicted wait for your next transfer, from the model's feature contributions. “Later” means it adds days; “earlier” means it saves days.")}</p>} /></div>
            {fd.map((x, i) => (
              <div className="barrow" key={i}>
                <div className="row between small"><span>{ft(x.feature)}</span><span className="muted">{x.effect_days > 0 ? t('adds ~{n} days', { n: x.effect_days.toFixed(1) }) : t('saves ~{n} days', { n: Math.abs(x.effect_days).toFixed(1) })}</span></div>
                <div className="hbar"><div style={{ width: `${(Math.abs(x.effect_days) / maxF) * 100}%`, background: x.effect_days > 0 ? 'var(--amber)' : 'var(--green)' }} /></div>
              </div>
            ))}
            {!fd.length && <p className="muted small">–</p>}
          </section>
          {d.warning_drivers.length > 0 && (
            <section className="card">
              <div className="row between"><h2>{t('Why we expect a shortfall')}</h2><AI label="Top reasons" why={<p>{t('These are the reasons the early-warning check found. A bigger bar means a bigger effect.')}</p>} /></div>
              {d.warning_drivers.map((x, i) => (
                <div className="barrow" key={i}><div className="row between small"><span>{tb(x.detail)}</span><b className="txt-red">{Math.round(x.magnitude * 100)}%</b></div><div className="hbar"><div style={{ width: `${x.magnitude * 100}%`, background: 'var(--red)' }} /></div></div>
              ))}
            </section>
          )}
        </div>
      </div>

      {ev && (
        <section className="card">
          <h2>{t('What following the plan could mean (simulated)')}</h2>
          <div className="simbanner"><b>{t('Simulated, not measured.')}</b> {t('Compliance is an assumption; a real pilot would measure it.')}</div>
          <table style={{ marginTop: 8 }}><thead><tr><th>{t('If the family follows the plan in…')}</th>{[0.6, 0.8, 1.0].map((c) => <th key={c}>{t('{p} of cycles', { p: pct(c) })}</th>)}</tr></thead>
            <tbody>{[['Bills on time', 'on_time_rate', pct], ['Late fees / year', 'late_fees_per_year', taka], ['Kept in wallet after 24h', 'retained_share', pct]].map(([label, k, fmt]) => (
              <tr key={k}><td>{t(label)}</td>{[0.6, 0.8, 1.0].map((c) => <td key={c}><b>{fmt(ev.compare.summary.find((r) => r.policy === 'remitwise' && r.compliance === c)[k])}</b></td>)}</tr>))}</tbody></table>
          <p className="tiny muted" style={{ marginTop: 6 }}>{t('Average of synthetic test households. Without a plan: {p} of bills on time.', { p: pct(ev.compare.summary.find((r) => r.policy === 'baseline').on_time_rate) })}</p>
        </section>
      )}

      {hist && (
        <section className="card">
          <div className="row between"><h2>{t('{name} bill: last {n} months and next month', { name: tb(hist.name), n: hist.points.length - 1 })}</h2><AI label={t('AI estimate for {m}', { m: hist.points[hist.points.length - 1].label })} why={<p>{t('The estimate for the next bill uses the same month last year. On our synthetic data this is about 10% off on average, versus about 16% for “same as last month”.')}</p>} /></div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer>
              <BarChart data={hist.points} margin={{ top: 22 }}>
                <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} />
                <YAxis hide domain={[0, 'dataMax + 300']} />
                <RBar dataKey="amount" radius={[8, 8, 0, 0]} isAnimationActive={false}>
                  {hist.points.map((p, i) => <Cell key={i} fill={p.estimate ? '#dcd3fb' : '#0d56a5'} stroke={p.estimate ? '#6a4bd8' : 'none'} strokeDasharray={p.estimate ? '5 4' : undefined} />)}
                  <LabelList dataKey="amount" position="top" formatter={(v) => taka(v)} fontSize={11} />
                </RBar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
      <p className="tiny muted">{t('AI values are estimates. All amounts are calculated in code; the AI only explains them.')}</p>
    </div>
  )
}
