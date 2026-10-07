import { useState } from 'react'
import { api } from './api'
import { t } from './i18n'

// Email security codes after sign-up and in the forgot-password flow. If the server has email set up the code arrives in the
// inbox; in demo mode (no email server) the API returns the code and we show it on screen.
const DemoCode = ({ code, note }) => code ? (
  <div className="demoCode" role="status">
    <small>{t('Demo mode: the code is shown here instead of being emailed.')}</small>
    <div>{t('Your code:')} <b>{code}</b></div>
  </div>
) : null

const CodeField = ({ value, onChange }) => (
  <div><label>{t('6-digit code')}</label><input value={value} onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" required minLength={6} maxLength={6} /></div>
)

export function VerifyEmail({ token, user, onDone }) {
  const [sent, setSent] = useState(null)
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async (fn) => { setErr(''); setBusy(true); try { await fn() } catch (ex) { setErr(ex.message) } finally { setBusy(false) } }
  const send = () => run(async () => setSent(await api('/auth/otp/request', { method: 'POST', body: {}, token })))
  const verify = (e) => { e.preventDefault(); run(async () => { const d = await api('/auth/otp/verify', { method: 'POST', body: { code }, token }); onDone(d.user) }) }
  return (
    <div className="card authcard">
      <h2>{t('Verify your email')}</h2>
      <p className="small muted" style={{ margin: '6px 0 12px' }}>{t('{name}, we will send a 6-digit security code to your email so we know it is really yours and can help you recover your account.', { name: user.name.split(' ')[0] })}</p>
      {!sent ? (
        <div className="form">
          <p className="small"><b>{user.email}</b></p>
          {err && <p className="small txt-red" role="alert">{err}</p>}
          <button className="btn primary block" disabled={busy} onClick={send}>{busy ? t('Please wait…') : t('Email me a code')}</button>
        </div>
      ) : (
        <form className="form" onSubmit={verify}>
          {sent.emailed ? <p className="small" role="status">{t('We sent a code to {to}. Check your inbox (and spam).', { to: sent.to })}</p> : <p className="small muted">{t('Code for {to}', { to: sent.to })}</p>}
          <DemoCode code={sent.demo_code} />
          <CodeField value={code} onChange={setCode} />
          <small className="muted">{t('The code works for 5 minutes and allows 5 tries.')}</small>
          {err && <p className="small txt-red" role="alert">{err}</p>}
          <button className="btn primary block" disabled={busy}>{busy ? t('Please wait…') : t('Verify email')}</button>
          <button type="button" className="link" onClick={() => { setCode(''); send() }}>{t('Send a new code')}</button>
        </form>
      )}
      <button className="link gray" style={{ marginTop: 12 }} onClick={() => onDone(null)}>{t('Skip for now')}</button>
    </div>
  )
}

export function ForgotPassword({ onBack }) {
  const [email, setEmail] = useState('')
  const [step, setStep] = useState('ask')
  const [info, setInfo] = useState(null)
  const [code, setCode] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const run = async (fn) => { setErr(''); setBusy(true); try { await fn() } catch (ex) { setErr(ex.message) } finally { setBusy(false) } }
  const request = (e) => { e.preventDefault(); run(async () => { setInfo(await api('/auth/reset/request', { method: 'POST', body: { email } })); setStep('confirm') }) }
  const confirm = (e) => { e.preventDefault(); run(async () => { await api('/auth/reset/confirm', { method: 'POST', body: { email, code, new_password: pw } }); setDone(true) }) }
  return (
    <div className="card authcard">
      <h2>{t('Reset your password')}</h2>
      {done ? (<>
        <p className="small" style={{ margin: '10px 0' }}>{t('Password changed. Sign in with your new password.')}</p>
        <button className="btn primary block" onClick={onBack}>{t('Back to sign in')}</button>
      </>) : step === 'ask' ? (
        <form className="form" onSubmit={request}>
          <p className="small muted">{t('Enter the email of your account. We will email you a 6-digit security code.')}</p>
          <div><label>{t('Email')}</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={120} autoComplete="email" /></div>
          {err && <p className="small txt-red" role="alert">{err}</p>}
          <button className="btn primary block" disabled={busy}>{busy ? t('Please wait…') : t('Email me a code')}</button>
        </form>
      ) : (
        <form className="form" onSubmit={confirm}>
          <p className="small muted">{t('If an account matches, a code has been sent to that email address.')}</p>
          <DemoCode code={info?.demo_code} />
          <CodeField value={code} onChange={setCode} />
          <div><label>{t('New password (at least 8 characters)')}</label><input type="password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} maxLength={128} autoComplete="new-password" /></div>
          <small className="muted">{t('Changing your password signs you out everywhere.')}</small>
          {err && <p className="small txt-red" role="alert">{err}</p>}
          <button className="btn primary block" disabled={busy}>{busy ? t('Please wait…') : t('Change password')}</button>
        </form>
      )}
      {!done && <button className="link gray" style={{ marginTop: 12 }} onClick={onBack}>{t('Back to sign in')}</button>}
    </div>
  )
}
