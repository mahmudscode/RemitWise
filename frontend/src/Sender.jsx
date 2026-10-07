import { useEffect, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { Bar, LangToggle } from './ui'
import { t, tb } from './i18n'

const days = (a, b) => Math.max(1, Math.round((new Date(b + 'T00:00:00') - new Date(a + 'T00:00:00')) / 86400000))

export default function Sender({ hid, state, tick, H, act, person, go, me, logout, lang, changeLang }) {
  const [data, setData] = useState(null)
  const [note, setNote] = useState('')
  const sid = `S-${hid}`

  useEffect(() => { api(`/sender/${sid}/goals`, H).then(setData).catch((e) => setData({ error: e.message })) /* eslint-disable-next-line */ }, [hid, tick])
  if (!data) return <p className="muted" style={{ padding: 24 }}>{t('Loading…')}</p>
  if (data.error) return <p className="error" style={{ margin: 24 }}>{data.error}</p>
  const c = data.consent
  const b = data.bills
  const ask = (scope) => act(() => api(`/sender/${sid}/request`, { ...H, method: 'POST', body: { scope } })).catch(() => {})
  const plan = () => act(async () => {
    const inDays = b?.send_by ? days(data.today, b.send_by) : 7
    const r = await api(`/sender/${sid}/intent`, { ...H, method: 'POST', body: { in_days: inDays, amount: b?.suggested_amount || 25000 } })
    setNote(`${tb(r.note)} ${t('(Demo: no real money is sent.)')}`)
  }).catch(() => {})

  const header = (
    <>
      <div className="topbar desk"><div className="row"><span className="logo">R</span><b style={{ fontSize: 20 }}>RemitWise</b></div>
        <div className="row"><LangToggle lang={lang} onChange={changeLang} /><span className="muted small">{(me?.role === 'sender' ? me.name : person?.sender_name) || 'Rahim'} · {t('Sender view')} · {person?.sender_city || 'Dubai'}</span>{me?.role === 'admin' && <button className="btn sm" onClick={() => go('home')}>{t('Switch to family view')}</button>}<button className="btn sm" onClick={logout}>{t('Log out')}</button></div></div>
      <div className="senderhead"><div className="row between"><span className="small" style={{ opacity: .85 }}>{t('Sender view')} <LangToggle lang={lang} onChange={changeLang} dark /></span><button className="btn sm" style={{ background: 'transparent', color: '#fff', borderColor: 'rgba(255,255,255,.5)' }} onClick={me?.role === 'admin' ? () => go('home') : logout}>{me?.role === 'admin' ? t('Family view') : t('Log out')}</button></div>
        <h1 style={{ fontSize: 26, margin: '6px 0 2px' }}>{t('Hi {name}', { name: me?.role === 'sender' ? me.name.split(' ')[0] : person?.sender_name })} 👋</h1><p style={{ opacity: .85 }}>{t('Here is how your family is doing back home.')}</p></div>
    </>
  )

  return (
    <div style={{ minHeight: '100vh' }}>
      {header}
      <div className="senderwrap stackv">
        <div className="only-desktop"><h1 style={{ fontSize: 30 }}>{t('Hi {name}', { name: me?.role === 'sender' ? me.name.split(' ')[0] : person?.sender_name })}</h1><p className="muted">{t('Here is how things look for your family back home this month.')}</p></div>

        {!c.sender_accepted && (
          <section className="card info"><h2>{t('Accept the family link')}</h2><p className="small muted" style={{ margin: '4px 0 10px' }}>{t('You only see what the family chooses to share. This protects trust and prevents monitoring of family spending.')}</p>
            <button className="btn primary" onClick={() => act(() => api(`/sender/${sid}/accept`, { ...H, method: 'POST' }))}>{t('Accept the family link')}</button></section>
        )}

        <div className="grid2e">
          {b ? (
            <section className={`card ${b.status === 'all_covered' ? 'green' : 'amber'}`}>
              <h2 className={b.status === 'all_covered' ? 'txt-green' : 'txt-amber'} style={{ fontSize: 20 }}>{b.status === 'all_covered' ? t('All bills & EMI covered this month') : t(b.at_risk_count > 1 ? '{n} payments at risk' : '{n} payment at risk', { n: b.at_risk_count })}</h2>
              {b.review_count > 0 && <p className="small" style={{ marginTop: 6 }}>{t(b.review_count > 1 ? '{n} bills are being reviewed by the family (unusual amount).' : '{n} bill is being reviewed by the family (unusual amount).', { n: b.review_count })}</p>}
              <p className="small muted" style={{ marginTop: 6 }}>{t('{a} of {b} paid · {c} scheduled from the bill vault', { a: b.paid_count, b: b.total_count, c: b.scheduled_from_vault })}</p>
              {b.family_asked && <p className="small" style={{ marginTop: 8 }}>💬 {t('The family asked if an earlier transfer is possible. It is your decision.')}</p>}
            </section>
          ) : (
            <section className="card"><h2>{t('Bills & EMI')}</h2><p className="small muted" style={{ margin: '6px 0' }}>{t('Not shared yet. The family decides what you can see.')}</p>{c.sender_accepted && c.scopes.bills_status !== 'requested' && <button className="btn sm" onClick={() => ask('bills_status')}>{t('Ask the family')}</button>}{c.scopes.bills_status === 'requested' && <span className="small muted">{t('Requested…')}</span>}</section>
          )}

          {b && (
            <section className="card">
              <div className="row between"><span className="muted">{t('Next transfer')}</span><span className="ai">{t('AI suggestion')}</span></div>
              {b.send_by ? (<>
                <p className="big">{t('Send by {d}', { d: fmtDate(b.send_by) })}</p>
                <p className="muted small">{t('Sending about {amt} by {d} keeps every bill on time', { amt: taka(b.suggested_amount), d: fmtDate(b.send_by) })}{b.shortfall_date ? t(' and avoids a shortfall around {d}', { d: fmtDate(b.shortfall_date) }) : ''}.</p>
              </>) : (<>
                <p className="big">{t('No rush')}</p>
                <p className="muted small">{t('Your family looks covered. The next transfer is expected around {d}. A transfer of about {amt} would keep things comfortable.', { d: fmtDate(b.next_expected), amt: taka(b.suggested_amount) })}</p>
              </>)}
              <button className="btn primary block" style={{ marginTop: 12 }} disabled={!c.sender_accepted} onClick={plan}>{t('Plan this transfer')}</button>
              {note && <p className="small" style={{ marginTop: 8 }}>{note}</p>}
            </section>
          )}
        </div>

        <section className="card">
          <h2 style={{ marginBottom: 10 }}>{t('Shared goals')}</h2>
          {data.goals.length === 0 && <p className="muted small">{data.message ? tb(data.message) : t('No goals shared yet.')}{c.sender_accepted && c.scopes.goal_progress !== 'granted' && c.scopes.goal_progress !== 'requested' && <> <button className="link" onClick={() => ask('goal_progress')}>{t('Ask the family')}</button></>}</p>}
          <div className="grid2e">{data.goals.map((g) => (
            <div key={g.name} style={{ margin: '4px 0' }}>
              <div className="row between"><b>{g.name}</b><b className={g.on_track ? 'txt-blue' : 'txt-amber'}>{g.pct}% · {g.on_track ? t('on track') : t('slightly behind')}</b></div>
              <Bar pct={g.pct} tone={g.on_track ? '' : 'amber'} />
            </div>))}
          </div>
          {data.savings_total != null && <p className="small" style={{ marginTop: 8 }}>{t('Family savings (shared with you):')} <b>{taka(data.savings_total)}</b></p>}
        </section>

        {data.recent_transfers?.length > 0 && (
          <section className="card">
            <h2 style={{ marginBottom: 8 }}>{t('Your recent transfers')}</h2>
            {data.recent_transfers.map((tr, i) => (
              <div className="row between" key={i} style={{ padding: '8px 0', borderTop: i ? '1px solid var(--line)' : 0 }}>
                <div><b>{fmtDate(tr.date)}</b>{tr.split && <div className="small muted">{t('Split: bills {a} · needs {b} · savings {c}', { a: taka(tr.split.bills), b: taka(tr.split.needs), c: taka(tr.split.savings) })}</div>}</div>
                <b style={{ fontSize: 18 }}>{taka(tr.amount)}</b>
              </div>
            ))}
          </section>
        )}

        <section className="card" style={{ background: 'transparent', borderStyle: 'dashed' }}>
          <p className="small muted">🔒 {t('You see goal progress and payment status only. Detailed spending stays private to your family unless they choose to share it.')}</p>
          <div className="row wrap small" style={{ marginTop: 8, gap: 14 }}>
            {[['goal_progress', t('Goal progress')], ['savings_total', t('Total savings')], ['bills_status', t('Bills & EMI status')]].map(([k, label]) => (
              <span key={k}>{label}: {c.scopes[k] === 'granted' ? t('✓ shared') : c.scopes[k] === 'requested' ? t('requested…') : <>{t('not shared')} {c.sender_accepted && <button className="link" onClick={() => ask(k)}>{t('Ask')}</button>}</>}</span>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
