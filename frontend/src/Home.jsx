import { useEffect, useState } from 'react'
import { api, fmtDate, longDate, taka } from './api'
import { AI, Avatar, Bar, Chip, ft, Modal, Projection, Skel } from './ui'
import { t, tb } from './i18n'
import { SpeakButton, VoiceAsk, digest } from './Voice.jsx'

export const subLine = (b) => {
  if (b.display_status === 'paid') return t('Paid {d}', { d: b.paid_date ? fmtDate(b.paid_date) : '' })
  if (!b.autopay) return t('Due {d} · paused', { d: fmtDate(b.due_date) })
  if (b.display_status === 'at_risk') return t('Due {d} · not fully covered', { d: fmtDate(b.due_date) })
  if (b.variable && b.amount == null) return t('Estimate · higher in summer · due {d}', { d: fmtDate(b.due_date) })
  return t('Due {d} · pays on due date', { d: fmtDate(b.due_date) })
}

export default function Home({ hid, state, tick, lang, H, go, person }) {
  // undefined = still loading (show a skeleton), null = loaded but not available
  const [home, setHome] = useState(undefined)
  const [fc, setFc] = useState(undefined)
  const [pj, setPj] = useState(undefined)
  const [sum, setSum] = useState(undefined)
  const [facts, setFacts] = useState(false)
  const [voiceNote, setVoiceNote] = useState('')

  useEffect(() => {
    api(`/households/${hid}/home`, H).then(setHome).catch(() => setHome(null))
    api(`/households/${hid}/forecast`, H).then(setFc).catch(() => setFc(null))
    api(`/households/${hid}/plan/projection`, H).then(setPj).catch(() => setPj(null))
    api(`/households/${hid}/summary?type=monthly&lang=${lang}`, H).then(setSum).catch(() => setSum(null))
    // eslint-disable-next-line
  }, [hid, tick, lang])

  const f = fc?.forecast
  const conf = f ? { high: 'high', medium: 'medium', low: 'low' }[fc.confidence_label] : ''
  const confPct = f ? Math.max(10, Math.min(100, Math.round(100 - ((f.rem_p90 - f.rem_p10) / 40) * 100))) : 0
  const safe = home?.safe

  return (
    <div className="stackv">
      <div className="pagehead">
        <div>
          <p className="eyebrow only-mobile">{t('Family wallet')}</p>
          <h1>{t('Good morning, {name}', { name: person?.name })}</h1>
          <p className="only-desktop">{longDate(state.date)} · {t('Family wallet')}</p>
        </div>
        <div className="row voicerow"><SpeakButton lang={lang} text={() => digest({ home, fc }, { t, taka, fmtDate, tb })} onNote={setVoiceNote} /><VoiceAsk lang={lang} home={home} fc={fc} /><button className="btn primary only-desktop" onClick={() => go('payments', { add: true })}>{t('+ Add payment')}</button><Avatar text={person?.name} /></div>
      </div>

      {voiceNote && <p className="small txt-amber" role="status">{voiceNote}</p>}
      <div className="grid3">
        <section className="card blue">
          <p className="bal-label">{t('Available balance')}</p>
          <p className="bal-big">{taka(home?.available ?? state.spendable)}</p>
          <span className="pill-dark">{t('{amt} reserved for bills & EMI', { amt: taka(home?.reserved_bills ?? state.vault) })}</span>
        </section>

        <section className="card">
          <div className="row between"><span className="muted">{t('Next remittance')}</span><AI why={<WhyForecast fc={fc} />} /></div>
          {fc === undefined ? <Skel lines={3} /> : f ? (<>
            <p className="big">{t('Expected in {a}–{b} days', { a: Math.round(f.rem_p10), b: Math.round(f.rem_p90) })}</p>
            <p className="muted small">{t('About {a} – {b} from {who} ({city})', { a: taka(f.amt_p10), b: taka(f.amt_p90), who: person?.sender_name, city: person?.sender_city })}</p>
            <Bar pct={confPct} />
            <div className="row between small muted"><span>{t('Confidence: {c}', { c: t(conf) })}{f.overdue ? t(' · overdue, range widened') : ''}</span><WhyLink fc={fc} /></div>
          </>) : <p className="muted" style={{ marginTop: 8 }}>{t('Collecting more history…')}</p>}
          <p className="explainer">{t('Budget apps track what you spent. RemitWise predicts when money will arrive and plans around that uncertainty.')}</p>
        </section>

        <section className="card">
          <div className="row between"><span className="muted">{t('Safe to spend')}</span><AI label="Estimate" title="How this is worked out" why={<WhySafe s={safe} />} /></div>
          {home === undefined ? <Skel lines={3} /> : safe ? (<>
            <p className="big txt-green" style={safe.status === 'amber' ? { color: 'var(--amber)' } : safe.status === 'red' ? { color: 'var(--red)' } : null}>{taka(safe.per_day)} <small>{t('/ day')}</small></p>
            <Bar tone={safe.status === 'green' ? 'green' : safe.status} pct={(safe.per_day / Math.max(safe.usual_per_day, 1)) * 100} />
            <p className="small muted">{t('Until your next expected transfer (about {n} days), without missing any bill. You usually spend about {amt} a day.', { n: safe.days, amt: taka(safe.usual_per_day) })}</p>
          </>) : <p className="muted" style={{ marginTop: 8 }}>{t('Available once a forecast exists.')}</p>}
        </section>
      </div>

      {home?.alert && (
        <div className={`banner ${home.alert.severity === 'red' ? 'red' : ''}`}>
          <span>{t(home.alert.days_short === 1 ? 'Heads up: you may run short about {n} day before your next transfer.' : 'Heads up: you may run short about {n} days before your next transfer.', { n: home.alert.days_short })}</span>
          <span className="row"><SpeakButton small lang={lang} text={() => t('Heads up: you may run short about {n} days before your next transfer.', { n: home.alert.days_short })} onNote={setVoiceNote} /><button className="link" onClick={() => go('plan')}>{t('See options →')}</button></span>
        </div>
      )}

      <div className="grid2">
        <section className="card only-desktop">
          <div className="row between"><h2>{t('Projected balance until next transfer')}</h2><AI label="AI forecast" /></div>
          {pj === undefined ? <Skel block={210} /> : <Projection pj={pj} height={210} />}
        </section>
        <section className="card">
          <div className="row between" style={{ marginBottom: 10 }}><h2>{t('Upcoming payments')}</h2><button className="link" onClick={() => go('payments')}>{t('See all')}</button></div>
          {home === undefined && <Skel lines={3} />}
          {home !== undefined && (home?.upcoming || []).length === 0 && <p className="muted small">{t('Nothing due soon.')}</p>}
          {(home?.upcoming || []).map((b) => (
            <div className="item" key={b.key} style={{ cursor: 'default' }} onClick={() => go('payments')}>
              <Avatar text={b.name} />
              <div className="grow"><b>{tb(b.name)}</b><small>{subLine(b)}</small></div>
              <div className="right"><b>{taka(b.amount ?? b.expected)}</b><Chip status={b.display_status} /></div>
            </div>
          ))}
        </section>
      </div>

      <div className="grid2" style={{ gridTemplateColumns: '1.35fr 1fr' }}>
        <section className="card purple">
          <span className="row between"><span className="ai" style={{ background: 'transparent', padding: 0 }}>{t('AI summary')}</span>{sum?.text && <SpeakButton small lang={lang} text={sum.text} onNote={setVoiceNote} />}</span>
          {sum === undefined ? <Skel lines={3} /> : sum ? (<>
            <p style={{ margin: '8px 0', fontSize: 15 }}>{sum.text}</p>
            <span className="tag">{tb(sum.label)} · {sum.source}</span> <button className="link" onClick={() => setFacts(!facts)}>{facts ? t('Hide the facts used') : t('Show the facts used')}</button>
            {facts && <pre>{JSON.stringify(sum.source_facts, null, 1)}</pre>}
          </>) : <p className="muted">–</p>}
        </section>
        <section className="card">
          <div className="row between" style={{ marginBottom: 6 }}><h2>{t('Goals')}</h2><button className="link" onClick={() => go('goals')}>{t('View all')}</button></div>
          {state.goals.length === 0 && <p className="muted small">{t('No goals yet.')}</p>}
          {state.goals.slice(0, 3).map((g) => (
            <div key={g.id} style={{ margin: '10px 0' }}>
              <div className="row between"><span>{tb(g.name)}</span><b className="txt-blue">{Math.round(g.pct)}%</b></div>
              <Bar pct={g.pct} />
            </div>
          ))}
        </section>
      </div>
    </div>
  )
}

function WhyLink({ fc }) {
  const [open, setOpen] = useState(false)
  return <><button className="link" onClick={() => setOpen(true)}>{t('Why?')}</button>{open && <Modal title={t('Why this estimate?')} onClose={() => setOpen(false)}><WhyForecast fc={fc} /></Modal>}</>
}

export const WhyForecast = ({ fc }) => (
  <div>
    <p>{t('This is a forecast made when your last transfer arrived. It looks at how often and how much your sender usually sends, the time of year, and recent delays.')}</p>
    {fc?.drivers?.length > 0 && <ul className="why">{fc.drivers.map((d, i) => <li key={i}>{ft(d.feature)}: {t(d.effect_days > 0 ? 'adds about {n} days' : 'saves about {n} days', { n: Math.abs(d.effect_days).toFixed(1) })}</li>)}</ul>}
    {fc?.forecast?.adjust_days != null && Math.abs(fc.forecast.adjust_days) >= 1 && <p className="small"><b>{t('Adjusted for your household:')}</b> {fc.forecast.adjust_days > 0 ? '+' : ''}{fc.forecast.adjust_days} {t('days')} ({fc.forecast.adjust_days > 0 ? t('your transfers have been later than predicted recently') : t('your transfers have been earlier than predicted recently')}).</p>}
    {fc?.forecast?.naive && <p className="small muted">{t('A simple “same as last time” guess would say {n} days and {amt}.', { n: fc.forecast.naive.gap, amt: taka(fc.forecast.naive.amt) })}</p>}
    <p className="small muted">{t('If the transfer is late, the range is widened instead of pretending the forecast still holds.')}</p>
  </div>
)
const WhySafe = ({ s }) => (
  <div>
    <p>{t('We take the money you can spend, subtract bills that are not yet covered ({amt}), and divide by the days until your next transfer is likely to arrive, leaning toward the later end so a late transfer does not catch you out.', { amt: taka(s?.bills_not_yet_covered) })}</p>
    <p className="small muted">{t('It is a guide, not a limit. You decide what to spend.')}</p>
  </div>
)
