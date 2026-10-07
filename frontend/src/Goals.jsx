import { useEffect, useRef, useState } from 'react'
import { api, fmtDate, taka } from './api'
import { AI, Bar, Modal, Toggle } from './ui'
import { t, tb } from './i18n'

export default function Goals({ hid, state, H, act, tick, person, me }) {
  const [copied, setCopied] = useState(false)
  const [consent, setConsent] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [addFor, setAddFor] = useState(null)
  const [amt, setAmt] = useState('')
  const [form, setForm] = useState({ name: '', target: '', days: 240 })
  const [sug, setSug] = useState(null)
  const [hint, setHint] = useState(null)
  const [msg, setMsg] = useState('')
  const [micro, setMicro] = useState(null)
  const [delText, setDelText] = useState('')
  const [delOpen, setDelOpen] = useState(false)
  const [agree, setAgree] = useState(false)
  const [yAgree, setYAgree] = useState(false)
  const timer = useRef(null)

  useEffect(() => {
    api(`/households/${hid}/consent`, H).then(setConsent).catch(() => {})
    api(`/households/${hid}/micro`, H).then(setMicro).catch(() => setMicro(null))
    api(`/households/${hid}/goals/suggest`, { ...H, method: 'POST', body: { target: 1000, days: 30 } }).then(setHint).catch(() => {})
    // eslint-disable-next-line
  }, [hid, tick])
  useEffect(() => {
    clearTimeout(timer.current)
    if (!form.target || +form.target <= 0) { setSug(null); return }
    timer.current = setTimeout(() => api(`/households/${hid}/goals/suggest`, { ...H, method: 'POST', body: { target: +form.target, days: +form.days } }).then(setSug).catch(() => setSug(null)), 300)
    // eslint-disable-next-line
  }, [form.target, form.days, hid])

  const saved = state.goals.reduce((a, g) => a + g.current, 0)
  const planned = state.goals.reduce((a, g) => a + (g.pace.per_month || 0), 0)
  const shared = state.goals.filter((g) => g.shared).length
  const tone = (g) => (g.pace.on_track === false ? 'amber' : g.pct >= 50 ? 'green' : '')
  const saveMicro = (patch) => act(async () => setMicro(await api(`/households/${hid}/micro`, { ...H, method: 'POST', body: { enabled: micro.enabled, consent: agree, yield_consent: yAgree, ...patch } }))).catch(() => {})
  const withdrawYield = () => act(async () => setMicro(await api(`/households/${hid}/micro/yield/withdraw`, { ...H, method: 'POST', body: {} }))).catch(() => {})
  const create = async (e) => {
    e.preventDefault(); setMsg('')
    await act(async () => {
      const r = await api(`/households/${hid}/goals`, { ...H, method: 'POST', body: { name: form.name, target: +form.target, days: +form.days, priority: 2 } })
      setMsg(r.feasible ? t('Needs about {amt} per transfer.', { amt: taka(r.per_transfer_needed) }) : tb(r.note))
      setForm({ name: '', target: '', days: 240 }); setSug(null); setShowNew(false)
    }).catch(() => {})
  }

  return (
    <div className="stackv">
      <div className="pagehead">
        <div><h1>{t('Goals')}</h1><p><span className="only-mobile">{t('Saving together with {who}', { who: person?.sender_name })}</span><span className="only-desktop">{t('Saving together, step by step')}</span></p></div>
        <button className="btn primary" onClick={() => setShowNew(true)}>{t('+ New goal')}</button>
      </div>

      <div className="grid3 only-desktop">
        <section className="card blue"><p className="bal-label">{t('Saved toward goals')}</p><p className="bal-big" style={{ fontSize: 34 }}>{taka(saved)}</p><p className="small" style={{ opacity: .9 }}>{t(state.goals.length === 1 ? 'across {n} goal' : 'across {n} goals', { n: state.goals.length })}</p></section>
        <section className="card tile"><small>{t('Planned each month')}</small><b>{planned ? taka(planned) : '–'}</b><span className="foot">{t('at your recent pace')}</span></section>
        <section className="card tile"><small>{t('Shared with {who}', { who: person?.sender_name })}</small><b>{t(shared === 1 ? '{n} goal' : '{n} goals', { n: shared })}</b><span className="foot">{t('progress only')}</span></section>
      </div>

      <div className="grid3">
        {state.goals.map((g) => {
          const p = g.pace
          return (
            <section className="card" key={g.id}>
              <div className="row between"><h2>{tb(g.name)}</h2><b className={p.on_track === false ? 'txt-amber' : g.pct >= 50 ? 'txt-green' : 'txt-blue'}>{Math.round(g.pct)}%</b></div>
              <p className="muted small" style={{ margin: '4px 0' }}>{t('{a} of {b}', { a: taka(g.current), b: taka(g.target) })}</p>
              <Bar pct={g.pct} tone={tone(g)} />
              <div className="row only-desktop between small" style={{ marginTop: 6 }}><span className="muted">{t('Target')}</span><b>{fmtDate(p.target_date)}</b></div>
              <div className="row only-desktop between small"><span className="muted">{t('Monthly plan')}</span><b>{t('{amt} / month', { amt: taka(p.required_per_month) })}</b></div>
              <div className="row between wrap small" style={{ margin: '8px 0', gap: 6 }}>
                <b className={p.on_track === false ? 'txt-amber' : p.on_track ? 'txt-green' : 'muted'} style={{ fontWeight: 600 }}>
                  {p.on_track === false ? t('Behind · add {amt}/month to catch up', { amt: taka(p.catch_up) }) : p.on_track ? t(Math.max(1, Math.round(p.months || 1)) === 1 ? 'On track · at this pace, {n} month' : 'On track · at this pace, {n} months', { n: Math.max(1, Math.round(p.months || 1)) }) : tb(p.text)}
                </b>
                <AI label="AI estimate" title="How this is estimated" why={<p>This uses your last few contributions to this goal and how often transfers usually arrive. It is an estimate and changes as your transfers change.</p>} />
              </div>
              <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10 }}>
                <Toggle checked={g.shared} label={g.shared ? t('Shared with {who}', { who: person?.sender_name }) : t('Private to family')} onChange={(on) => act(() => api(`/households/${hid}/goals/${g.id}/share`, { ...H, method: 'POST', body: { shared: on } }))} />
              </div>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn block" onClick={() => { setAddFor(g); setAmt('') }}>{t('Add money')}</button>
                <button className="link gray" onClick={() => act(() => api(`/households/${hid}/goals/${g.id}`, { ...H, method: 'DELETE' }))}>{t('Remove')}</button>
              </div>
            </section>
          )
        })}
      </div>

      {hint && hint.suggested_monthly > 0 && <section className="card info small">{t('Thinking of a new goal? Based on your forecast, about {amt} a month is realistic without risking bills.', { amt: taka(hint.suggested_monthly) })}</section>}
      {msg && <p className="small muted">{msg}</p>}

      {micro && (
        <section className="card">
          <div className="row between wrap"><h2>{t('Micro-savings')}</h2><span className="ai">{t('Savings, with an optional simulated yield pot')}</span></div>
          <p className="small muted" style={{ margin: '6px 0 10px' }}>{t('When on, a few taka move to your emergency fund or a goal at the end of each day, only when your bills are covered and no shortfall warning is active. It is off until you switch it on, and you can stop any time.')}</p>
          {!micro.enabled && <label className="check" style={{ marginBottom: 8 }}><input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />{t('I agree to move small amounts to savings automatically.')}</label>}
          <Toggle checked={micro.enabled} label={micro.enabled ? t('Micro-savings is on') : t('Micro-savings is off')} onChange={(on) => { if (on && !agree) { setMsg(t('Tick the box to agree first.')); return } setMsg(''); saveMicro({ enabled: on }) }} />
          <div className="row wrap" style={{ marginTop: 10, gap: 12 }}>
            <div className="grow"><label className="small muted">{t('How much')}</label>
              <select value={micro.mode} onChange={(e) => saveMicro({ mode: e.target.value })}>{micro.modes.map((m) => <option key={m.id} value={m.id}>{t(m.label)}</option>)}</select></div>
            <div className="grow"><label className="small muted">{t('Save into')}</label>
              <select value={micro.target} onChange={(e) => { if (e.target.value === 'yield' && !micro.yield_pot.consented && !yAgree) { setMsg(t('Tick the yield box to agree first.')); return } saveMicro({ target: e.target.value }) }}>{micro.targets.map((x) => <option key={x.id} value={x.id}>{tb(x.name)}</option>)}</select></div>
          </div>
          {!micro.yield_pot.consented && <label className="check" style={{ marginTop: 8 }}><input type="checkbox" checked={yAgree} onChange={(e) => setYAgree(e.target.checked)} />{t('I understand the yield pot is a simulation of a low-risk option, not a real product and not advice.')}</label>}
          {(micro.yield_pot.consented || micro.yield_pot.balance > 0) && (
            <div className="yieldbox">
              <div className="row between wrap"><b>{t('Simulated yield pot')}</b><span className="ai">{t('Simulated')}</span></div>
              <p style={{ margin: '6px 0' }}>{taka(micro.yield_pot.balance)} <span className="muted small">{t('({e} earned at an illustrative {r}% a year)', { e: taka(micro.yield_pot.earned), r: (micro.yield_pot.rate * 100).toFixed(1) })}</span></p>
              <button className="btn sm" disabled={micro.yield_pot.balance <= 0} onClick={withdrawYield}>{t('Withdraw all to wallet')}</button>
              <p className="tiny muted" style={{ marginTop: 6 }}>{t('Synthetic money and an illustrative rate. A real product could lose value. No lock-in, no fee, and it pauses when your bills are at risk.')}</p>
            </div>
          )}
          <div className="row between wrap" style={{ marginTop: 12 }}>
            <b>{t('Micro-saved this month: {amt}', { amt: taka(micro.month_total) })}</b>
            {micro.paused && <span className="chip amber">{t('Paused to protect your bills')}</span>}
            {micro.enabled && !micro.paused && <span className="chip green">{t('Saving')}</span>}
          </div>
          <p className="tiny muted" style={{ marginTop: 6 }}>{t('A few taka a day at most. Daily cash for the next two days is never touched. The yield pot is optional and simulated; nothing here is financial advice.')}</p>
        </section>
      )}

      <section className="card">
        <h2>{t('Sharing with {who}', { who: person?.sender_name })}</h2>
        {me?.role === 'family' && me.invite_code && (
          <div className="invite" style={{ margin: '10px 0' }}>
            <div className="grow"><small className="muted">{t('Invite your sender: they create a Sender account with this code')}</small><br /><code>{me.invite_code}</code></div>
            <button className="btn sm" onClick={() => { navigator.clipboard?.writeText(me.invite_code); setCopied(true); setTimeout(() => setCopied(false), 1500) }}>{copied ? t('Copied') : t('Copy')}</button>
          </div>
        )}
        <p className="small muted" style={{ margin: '4px 0 10px' }}>{t('{who} sees goal progress only, never your transactions, unless you choose to share more. You can change this any time, and you can say no to any request.', { who: person?.sender_name })}</p>
        {consent && (<>
          <p className="small">{t('Sender link:')} {consent.sender_accepted ? t('accepted ✓') : t('waiting for the sender to accept')}</p>
          <div className="stackv" style={{ gap: 10, marginTop: 8 }}>
            {[['goal_progress', t('Goal progress (the goals switched on above)')], ['savings_total', t('Total savings')], ['bills_status', t('Bills & EMI status, and a suggested send-by date')]].map(([k, label]) => (
              <Toggle key={k} checked={consent.scopes[k] === 'granted'} label={<>{label}{consent.scopes[k] === 'requested' && <em className="txt-amber"> · {t('{who} asked to see this', { who: person?.sender_name })}</em>}</>}
                onChange={(on) => act(() => api(`/households/${hid}/consent`, { ...H, method: 'POST', body: { scope: k, state: on ? 'granted' : 'revoked' } }))} />
            ))}
          </div>
          <p className="tiny muted" style={{ marginTop: 8 }}>{t('Spending details are not shared in this demo.')}</p>
        </>)}
      </section>

      {me && me.role !== 'admin' && !me.is_demo && (
        <section className="card">
          <h2>{t('Your data')}</h2>
          <p className="small muted" style={{ margin: '6px 0 8px' }}>{t('You can delete your account and its data at any time. Sessions expire after 30 days and the audit log is kept for 12 months.')} <a href="https://github.com/mahmudscode/RemitWise/blob/main/docs/data-retention.md" target="_blank" rel="noreferrer">{t('Read the data-retention policy')}</a></p>
          <button className="btn redo" onClick={() => setDelOpen(true)}>{t('Delete my account')}</button>
        </section>
      )}
      {delOpen && <Modal title={t('Delete my account')} onClose={() => setDelOpen(false)}>
        <form className="form" onSubmit={async (e) => { e.preventDefault(); try { await api('/me', { method: 'DELETE', body: { confirm: delText } }); window.dispatchEvent(new Event('rw-unauth')) } catch (ex) { setMsg(ex.message) } }}>
          <p className="small">{t('This permanently removes your account and data. Type DELETE to confirm.')}</p>
          <input value={delText} onChange={(e) => setDelText(e.target.value)} autoFocus />
          <button className="btn redo block" disabled={delText.trim().toUpperCase() !== 'DELETE'}>{t('Delete my account')}</button>
        </form>
      </Modal>}

      {showNew && <Modal title={t('New goal')} onClose={() => setShowNew(false)}>
        <form className="form" onSubmit={create}>
          <div><label>{t('Goal name')}</label><input placeholder={t('e.g. Education')} maxLength={40} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
          <div className="row"><div className="grow"><label>{t('Target ৳')}</label><input type="number" min="1" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} required /></div>
            <div className="grow"><label>{t('Days to deadline')}</label><input type="number" min="14" value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} /></div></div>
          {sug && <div className="suggest"><b>{t('Suggested: {amt} a month', { amt: taka(sug.suggested_monthly) })}</b> <AI label="Estimate" why={<p>{tb(sug.explanation)} {t('Your goal needs about {amt} a month for this deadline.', { amt: taka(sug.needed_monthly) })}</p>} /><br />
            <small className="muted">{sug.months_at_suggested ? t('About {n} months at that pace.', { n: sug.months_at_suggested }) : t('No spare money is expected right now.')} {sug.realistic ? '' : t('This deadline looks tight; consider a longer one.')}</small></div>}
          <button className="btn primary block">{t('Create goal')}</button>
        </form>
      </Modal>}
      {addFor && <Modal title={t('Add money to {name}', { name: tb(addFor.name) })} onClose={() => setAddFor(null)}>
        <form className="form" onSubmit={(e) => { e.preventDefault(); act(() => api(`/households/${hid}/goals/${addFor.id}/add_money`, { ...H, method: 'POST', body: { amount: +amt } })).then(() => setAddFor(null)).catch(() => {}) }}>
          <p className="muted small">{t('Available to move: {amt}', { amt: taka(state.spendable) })}</p>
          <input type="number" min="1" max={state.spendable} placeholder={t('Amount ৳')} value={amt} onChange={(e) => setAmt(e.target.value)} required autoFocus />
          <button className="btn primary block">{t('Move to goal')}</button>
        </form>
      </Modal>}
    </div>
  )
}
