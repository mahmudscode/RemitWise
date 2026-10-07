import { useEffect, useMemo, useState } from 'react'
import { api, fmtDate, monthName, taka } from './api'
import { AI, Avatar, Bar, Chip, DOT, Modal, Toggle } from './ui'
import { subLine } from './Home'
import { t, tb, locale, getLang } from './i18n'

export default function Payments({ hid, state, tick, H, act, openAdd, clearAdd }) {
  const [data, setData] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [why, setWhy] = useState(null)
  const [manage, setManage] = useState(null)
  const [form, setForm] = useState({ biller: '', kind: 'utility', account_number: '', usual_amount: '', due_day: 10, monthly_limit: '', confirm_over_limit: true })
  const [err, setErr] = useState('')

  useEffect(() => { api(`/households/${hid}/bills`, H).then(setData).catch(() => setData(null)) /* eslint-disable-next-line */ }, [hid, tick])
  useEffect(() => { if (openAdd) { setShowAdd(true); clearAdd?.() } }, [openAdd, clearAdd])

  const langNow = getLang()
  const view = useMemo(() => {
    if (!data) return null
    const td = new Date(data.today + 'T00:00:00')
    const m = td.getMonth(), y = td.getFullYear()
    const monthItems = data.items.filter((i) => { const d = new Date(i.due_date + 'T00:00:00'); return d.getMonth() === m && d.getFullYear() === y })
    const sum = (st) => monthItems.filter((i) => st.includes(i.display_status)).reduce((a, i) => a + (i.amount ?? i.expected), 0)
    const due = monthItems.reduce((a, i) => a + (i.amount ?? i.expected), 0)
    const byDay = {}
    monthItems.forEach((i) => (byDay[new Date(i.due_date + 'T00:00:00').getDate()] ||= []).push(i))
    const first = new Date(y, m, 1), days = new Date(y, m + 1, 0).getDate()
    const monday = new Date(td); monday.setDate(td.getDate() - ((td.getDay() + 6) % 7))
    const week = Array.from({ length: 7 }, (_, k) => { const d = new Date(monday); d.setDate(monday.getDate() + k); return d })
    const dayItems = (d) => data.items.filter((i) => i.due_date === d.toISOString().slice(0, 10) || i.due_date === `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
    return { today: td, due, paid: sum(['paid']), sched: sum(['scheduled']), risk: sum(['at_risk', 'overdue']), byDay, first, days, week, dayItems, label: td.toLocaleDateString(locale(), { month: 'long', year: 'numeric' }) }
  }, [data, langNow])

  if (!data) return <p className="muted">{t('Loading…')}</p>
  const flagged = data.items.filter((i) => i.display_status === 'needs_review')
  const list = data.items.filter((i) => i.display_status !== 'paid' || true).sort((a, b) => (a.display_status === 'paid') - (b.display_status === 'paid') || a.due_day - b.due_day)
  const reservedPct = view.due ? Math.round((data.vault / view.due) * 100) : 0
  const resolve = (key, action) => act(() => api(`/households/${hid}/bills/resolve?key=${encodeURIComponent(key)}`, { ...H, method: 'POST', body: { action } })).catch(() => {})
  const toggle = (bid, on) => act(() => api(`/households/${hid}/bills/${bid}/autopay`, { ...H, method: 'POST', body: { on } }))
  const pauseAll = () => act(async () => { for (const b of data.mandates) if (b.autopay) await api(`/households/${hid}/bills/${b.bill_id}/autopay`, { ...H, method: 'POST', body: { on: false } }) })
  const add = async (e) => {
    e.preventDefault(); setErr('')
    try {
      await act(() => api(`/households/${hid}/bills/mandates`, { ...H, method: 'POST', body: { ...form, usual_amount: +form.usual_amount, due_day: +form.due_day, monthly_limit: +form.monthly_limit } }))
      setShowAdd(false); setForm({ ...form, biller: '', account_number: '', usual_amount: '', monthly_limit: '' })
    } catch (ex) { setErr(ex.message) }
  }

  return (
    <div className="stackv">
      <div className="pagehead">
        <div><h1>{t('Payments')}</h1><p>{t('EMIs and bills on auto-pay')}</p></div>
        <div className="row"><button className="btn only-desktop" onClick={pauseAll}>{t('Pause all')}</button><button className="btn primary" onClick={() => setShowAdd(true)}>{t('+ Add')}<span className="only-desktop">&nbsp;{t('payment')}</span></button></div>
      </div>

      <div className="grid2e" style={{ gridTemplateColumns: flagged.length ? '1.1fr 1fr' : '1fr' }}>
        <section className="card">
          <div className="row between"><span className="muted">{t('Bill vault')} · {monthName(data.today)}</span><b className="txt-blue small">{t('{n}% reserved', { n: reservedPct })}</b></div>
          <p className="big" style={{ fontSize: 34 }}>{taka(data.vault)} <small>{t('of {amt} due this month', { amt: taka(view.due) })}</small></p>
          <Bar pct={reservedPct} />
          <div className="row only-desktop" style={{ gap: 28, marginTop: 6 }}>
            <div><small className="muted">{t('Paid')}</small><br /><b className="txt-blue" style={{ fontSize: 17 }}>{taka(view.paid)}</b></div>
            <div><small className="muted">{t('Scheduled')}</small><br /><b className="txt-green" style={{ fontSize: 17 }}>{taka(view.sched)}</b></div>
            <div><small className="muted">{t('At risk')}</small><br /><b className="txt-amber" style={{ fontSize: 17 }}>{taka(view.risk)}</b></div>
          </div>
        </section>

        {flagged.slice(0, 1).map((b) => (
          <section className="card red" key={b.key}>
            <div className="row between"><b className="txt-red small">{t('Needs review')}</b><span className="ai">{t('Unusual bill detected')}</span></div>
            <p style={{ fontSize: 20, fontWeight: 800, margin: '8px 0 4px' }}>{t('{name} bill {amt} is {x}× your usual amount', { name: tb(b.name), amt: taka(b.amount), x: (b.amount / b.expected).toFixed(1) })}</p>
            <p className="muted small">{b.usual_low ? t('Usual range {a} – {b} over the last 6 months. ', { a: taka(b.usual_low), b: taka(b.usual_high) }) : t('Usual amount about {amt}. ', { amt: taka(b.expected) })}{t('Auto-pay is paused until you decide.')}</p>
            <div className="row wrap" style={{ marginTop: 10 }}>
              <button className="btn red" onClick={() => resolve(b.key, 'approve')}>{t('Approve & pay')}</button>
              <button className="btn redo" onClick={() => resolve(b.key, 'dispute')}>{t('Dispute')}</button>
              <button className="link red" onClick={() => setWhy(b)}>{t('Why?')}</button>
              <button className="link gray" onClick={() => resolve(b.key, 'pay_manually')}>{t('Pay manually')}</button>
            </div>
          </section>
        ))}
      </div>

      <div className="grid2" style={{ gridTemplateColumns: '1.55fr 1fr' }}>
        <section className="card">
          <div className="row between" style={{ marginBottom: 10 }}>
            <h2><span className="only-mobile">{t('Auto-pay')}</span><span className="only-desktop">{t('Auto-pay mandates')}</span></h2>
            <span className="small muted only-desktop">{t('{n} active', { n: data.mandates.length })}</span>
            <button className="link only-mobile" onClick={() => setManage('list')}>{t('Manage')}</button>
          </div>
          <div className="week only-mobile" style={{ marginBottom: 12 }}>
            {view.week.map((d) => { const its = view.dayItems(d); const on = d.toDateString() === view.today.toDateString()
              return <div key={+d} className={`wk ${on ? 'on' : ''}`}>{d.toLocaleDateString(locale(), { weekday: 'short' })}<b>{d.getDate()}</b><span className="d">{its.slice(0, 3).map((x) => <i key={x.key} className={`dot ${on ? '' : DOT[x.display_status]}`} style={on ? { background: '#fff' } : null} />)}</span></div> })}
          </div>
          {list.length === 0 && <p className="muted small">{t('No payments set up yet.')}</p>}
          {list.map((b) => (
            <button className="item" key={b.key} onClick={() => setManage(b)}>
              <Avatar text={b.name} />
              <div className="grow"><b>{tb(b.name)}</b><small>{subLine(b)}{b.autopay && b.display_status !== 'paid' && b.monthly_limit < 1e6 ? t(' · limit {amt}', { amt: taka(b.monthly_limit) }) : ''}</small></div>
              <div className="right"><b>{taka(b.amount ?? b.expected)}</b><Chip status={b.display_status} /></div>
            </button>
          ))}
        </section>

        <section className="card only-desktop" style={{ alignSelf: 'start' }}>
          <h2 style={{ marginBottom: 8 }}>{view.label}</h2>
          <div className="cal">
            {[t('M'), t('T'), t('W'), t('T'), t('F'), t('S'), t('S')].map((d, i) => <span key={i} className="calh">{d}</span>)}
            {Array.from({ length: (view.first.getDay() + 6) % 7 }).map((_, i) => <span key={'p' + i} />)}
            {Array.from({ length: view.days }).map((_, i) => { const d = i + 1, its = view.byDay[d] || []
              return <div key={d} className={`calc ${d === view.today.getDate() ? 'today' : ''}`}>{d}<span className="d">{its.slice(0, 3).map((x) => <i key={x.key} className={`dot ${d === view.today.getDate() ? '' : DOT[x.display_status]}`} style={d === view.today.getDate() ? { background: '#fff' } : null} />)}</span></div> })}
          </div>
          <div className="legend" style={{ marginTop: 14 }}><span><i className="dot blue" />{t('Paid')}</span><span><i className="dot green" />{t('Scheduled')}</span><span><i className="dot amber" />{t('At risk')}</span><span><i className="dot red" />{t('Needs review')}</span></div>
        </section>
      </div>

      {why && <Modal title={t('Why was the {name} bill flagged?', { name: tb(why.name) })} onClose={() => setWhy(null)}>
        <p>{t('Billed:')} <b>{taka(why.amount)}</b>. {t('Usual estimate:')} <b>{taka(why.expected)}</b> {t('(same month last year). That is')} <b>{(why.amount / why.expected).toFixed(1)}×</b> {t('higher; we hold anything above 1.8× for your review.')}</p>
        <p className="small muted" style={{ marginTop: 8 }}>{t('If you dispute it, we assume it is corrected to the estimate before payment (a demo assumption).')}</p>
      </Modal>}

      {manage && manage !== 'list' && <Modal title={tb(manage.name)} onClose={() => setManage(null)}>
        <p className="muted small">{t('Due {d}', { d: fmtDate(manage.due_date) })} · {manage.variable ? t('variable bill') : t('fixed amount')}</p>
        <div className="stackv" style={{ marginTop: 12 }}>
          <Toggle label={t('Auto-pay on due date')} checked={manage.autopay} onChange={(on) => { toggle(manage.bill_id, on); setManage({ ...manage, autopay: on }) }} />
          <p className="small muted">{t('Monthly limit:')} {manage.monthly_limit > 1e8 ? t('none') : taka(manage.monthly_limit)} · {manage.confirm_over_limit ? t('asks you to confirm above it') : t('no confirmation')}</p>
          {manage.note && <p className="small">{tb(manage.note)}</p>}
          {data.mandates.find((m) => m.bill_id === manage.bill_id) && <button className="btn redo" onClick={() => { act(() => api(`/households/${hid}/bills/mandates/${manage.bill_id}`, { ...H, method: 'DELETE' })); setManage(null) }}>{t('Cancel this mandate')}</button>}
          <p className="tiny muted">{t('Pausing keeps the bill on your list. You pay it yourself.')}</p>
        </div>
      </Modal>}
      {manage === 'list' && <Modal title={t('Manage auto-pay')} onClose={() => setManage(null)}>
        <div className="stackv">
          {data.mandates.map((m) => <div className="row between" key={m.bill_id}><span><b>{tb(m.name)}</b><br /><small className="muted">{t('usual {amt} · due day {n}', { amt: taka(m.usual), n: m.due_dom })}</small></span><Toggle checked={m.autopay} onChange={(on) => { toggle(m.bill_id, on); setManage(null) }} /></div>)}
          <button className="btn" onClick={pauseAll}>{t('Pause all')}</button>
        </div>
      </Modal>}

      {showAdd && <Modal title={t('Add payment')} onClose={() => setShowAdd(false)}>
        <form className="form" onSubmit={add}>
          <div><label>{t('Biller')}</label><input placeholder={t('e.g. Water supply, Bike EMI')} value={form.biller} onChange={(e) => setForm({ ...form, biller: e.target.value })} required /></div>
          <div className="row"><div className="grow"><label>{t('Type')}</label><select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}><option value="utility">{t('Utility')}</option><option value="emi">{t('EMI / loan')}</option><option value="school">{t('School')}</option><option value="other">{t('Other')}</option></select></div>
            <div className="grow"><label>{t('Due day (1–28)')}</label><input type="number" min="1" max="28" value={form.due_day} onChange={(e) => setForm({ ...form, due_day: e.target.value })} required /></div></div>
          <div><label>{t('Account / customer number')}</label><input value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} required minLength={4} /></div>
          <div className="row"><div className="grow"><label>{t('Usual amount ৳')}</label><input type="number" min="1" value={form.usual_amount} onChange={(e) => setForm({ ...form, usual_amount: e.target.value })} required /></div>
            <div className="grow"><label>{t('Monthly limit ৳')}</label><input type="number" min="1" value={form.monthly_limit} onChange={(e) => setForm({ ...form, monthly_limit: e.target.value })} required /></div></div>
          <label className="check"><input type="checkbox" checked={form.confirm_over_limit} onChange={(e) => setForm({ ...form, confirm_over_limit: e.target.checked })} />{t('Ask me to confirm payments over the limit')}</label>
          {err && <p className="small txt-red">{err}</p>}
          <button className="btn primary block">{t('Set up auto-pay')}</button>
          <p className="tiny muted">{t('Demo only: no real account or money is connected.')}</p>
        </form>
      </Modal>}
    </div>
  )
}
