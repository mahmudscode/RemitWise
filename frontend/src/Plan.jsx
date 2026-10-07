import { useEffect, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { AI, CAT, Projection } from './ui'
import { t, tb } from './i18n'

export default function Plan({ hid, state, tick, H, act, person }) {
  const [pj, setPj] = useState(null)
  const [cats, setCats] = useState(null)
  const [opts, setOpts] = useState([])
  const [bills, setBills] = useState([])
  const [fc, setFc] = useState(null)
  const [pick, setPick] = useState(null)
  const [note, setNote] = useState('')

  useEffect(() => {
    api(`/households/${hid}/plan/projection`, H).then(setPj).catch(() => setPj(null))
    api(`/households/${hid}/plan/categories`, H).then(setCats).catch(() => setCats(null))
    api(`/households/${hid}/plan/options`, H).then((r) => { setOpts(r.options); setPick(r.options[0]?.id || null) }).catch(() => setOpts([]))
    api(`/households/${hid}/bills`, H).then((r) => setBills(r.items)).catch(() => {})
    api(`/households/${hid}/forecast`, H).then(setFc).catch(() => setFc(null))
    // eslint-disable-next-line
  }, [hid, tick])

  const asked = opts.find((o) => o.id === 'ask_sender')?.asked
  const total = (cats?.items || []).reduce((a, c) => a + c.amount, 0) || 1
  const f = fc?.forecast
  const coming = bills.filter((b) => ['scheduled', 'at_risk', 'needs_review'].includes(b.display_status) && f && b.due_day <= state.day + f.rem_p90)
  const apply = () => {
    const o = opts.find((x) => x.id === pick)
    if (!o) return
    if (!o.actionable) { setNote(t('Good choice: aim to spend about {amt} less per day until the transfer arrives. We will keep watching.', { amt: taka(o.amount) })); return }
    act(async () => { await api(`/households/${hid}/plan/options/apply`, { ...H, method: 'POST', body: { option: o.id } }); setNote(o.id === 'ask_sender' ? t('{who} has been asked. It is their decision.', { who: person?.sender_name }) : t('Moved. You can top the goals up later.')) }).catch(() => {})
  }

  return (
    <div className="stackv">
      <div className="pagehead"><div><h1>{t('Plan')}</h1><p>{t('Cash flow until your next transfer')}</p></div></div>
      <div className="grid2" style={{ gridTemplateColumns: '1.7fr 1fr' }}>
        <section className="card">
          <div className="row between"><h2>{t('Projected balance')}</h2><AI label="AI forecast" why={<div><p>{t('We simulate hundreds of possible futures for your daily spending and show the middle path with a shaded range (10th to 90th percentile). Bills and EMIs are paid from your bill vault first and appear as dots.')}</p><p className="small muted">{t('Where the line dips below zero it turns red: that is when you could run short.')}</p></div>} /></div>
          <Projection pj={pj} height={250} />
        </section>
        {opts.length > 0 ? (
          <section className="card amber" style={{ alignSelf: 'start' }}>
            <h2>{t('Choose how to avoid the shortfall')}</h2>
            <p className="small muted" style={{ margin: '4px 0 8px' }}>{t(opts.length > 1 ? 'The AI found {n} ways to stay above zero. You decide.' : 'The AI found {n} way to stay above zero. You decide.', { n: opts.length })}</p>
            {opts.map((o) => <button key={o.id} className={`opt ${pick === o.id ? 'on' : ''}`} onClick={() => setPick(o.id)}><span className="rad" />{tb(o.title)}</button>)}
            <button className="btn amber block" onClick={apply}>{t('Apply choice')}</button>
            {(note || asked) && <p className="small" style={{ marginTop: 8 }}>{note || t('{who} has been asked. It is their decision.', { who: person?.sender_name })}</p>}
          </section>
        ) : (
          <section className="card green" style={{ alignSelf: 'start' }}><h2>{t('You are on track')}</h2><p className="small muted" style={{ marginTop: 4 }}>{t('No shortfall is expected if your next transfer arrives on time. We will tell you early if that changes.')}</p></section>
        )}
      </div>

      <div className="grid2e" style={{ gridTemplateColumns: '1.7fr 1fr' }}>
        <section className="card">
          <div className="row between"><h2>{t('Spending this month')}</h2><AI label="Simulated" title="About these categories" why={<p>{t("Categories are simulated shares of each household's spending (an assumption), plus the bills you actually paid in the last 30 days.")}</p>} /></div>
          {(cats?.items || []).map((c) => (
            <div className="barrow" key={c.category}>
              <div className="row between"><span>{CAT[c.category] ? t(CAT[c.category][0]) : c.category}</span><span className="muted">{Math.round((c.amount / total) * 100)}%</span></div>
              <div className="hbar"><div style={{ width: `${(c.amount / total) * 100}%`, background: CAT[c.category]?.[1] }} /></div>
            </div>
          ))}
          <p className="tiny muted">{t('Last 30 days.')}</p>
        </section>
        <section className="card" style={{ alignSelf: 'start' }}>
          <h2 style={{ marginBottom: 8 }}>{t('Coming up before next transfer')}</h2>
          {coming.map((b) => (
            <div className="row between" key={b.key} style={{ padding: '5px 0', fontSize: 14 }}>
              <span><small className="muted">{fmtDate(b.due_date)}</small>&nbsp; {tb(b.name)}{b.variable && b.amount == null ? t(' (estimate)') : ''}</span>
              <b className={b.display_status === 'at_risk' ? 'txt-amber' : ''}>– {taka(b.amount ?? b.expected)}</b>
            </div>
          ))}
          {f && <div className="row between" style={{ padding: '5px 0', fontSize: 14 }}><span><small className="muted">{fmtDate(f.next_date_p10)}–{fmtDate(f.next_date_p90)}</small>&nbsp; {t('Remittance from {who}', { who: person?.sender_name })}</span><b className="txt-green">+ {taka(f.amt_p10)}–{taka(f.amt_p90)}</b></div>}
          {!coming.length && !f && <p className="muted small">{t('Nothing coming up.')}</p>}
        </section>
      </div>
    </div>
  )
}
