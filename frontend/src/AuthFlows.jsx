import { useState } from 'react'
import { api } from './api'
import { t } from './i18n'

// Phone verification after sign-up and the forgot-password flow. Codes are simulated: in demo mode the API returns
// the code and we show it on screen (no SMS is sent).
const DemoCode = ({ code }) => code ? (
  <div className="demoCode" role="status">
    <small>{t('Demo: no SMS is sent.')}</small>
    <div>{t('Your code:')} <b>{code}</b></div>
  </div>
) : null

export function VerifyPhone({ token, user, onDone }) {
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const call = (path, body) => api(path, { method: 'POST', body, token })
  const send = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { setSent(await call('/auth/otp/request', { phone })) } catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }
  const verify = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try { const d = await call('/auth/otp/verify', { code }); onDone(d.user) } catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }
  return (
    <div className="card authcard">
      <h2>{t('Verify your phone')}</h2>
      <p className="small muted" style={{ margin: '6px 0 12px' }}>{t('{name}, add your mobile number so you can recover your account and get important alerts.', { name: user.name.split(' ')[0] })}</p>
      {!sent ? (
        <form className="form" onSubmit={send}>
          <div><label>{t('Mobile number')}</label><input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="01712345678" inputMode="tel" required autoComplete="tel" /></div>
          {err && <p className="small txt-red" role="alert">{err}</p>}
          <button className="btn primary block" disabled={busy}>{busy ? t('Please wait…') : t('Send code')}</button>
        </form>
      ) : (
        <form className="form" onSubmit={verify}>
          <DemoCode code={sent.demo_code} />
          <div><label>{t('6-digit code')}</label><input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" required minLength={6} maxLength={6} /></div>
          <small className="muted">{t('The code works for 5 minutes and allows 5 tries.')}</small>
          {err && <p className="small txt-red" role="alert">{err}</p>}
          <button className="btn primary block" disabled={busy}>{busy ? t('Please wait…') : t('Verify phone')}</button>
          <button type="button" className="link" onClick={() => { setSent(null); setCode(''); setErr('') }}>{t('Use a different number or resend')}</button>
        </form>
      )}
      <button className="link gray" style={{ marginTop: 12 }} onClick={() => onDone(null)}>{t('Skip for now')}</button>
    </div>
  )
}

export function ForgotPassword({ onBack }) {
  const [identifier, setIdentifier] = useState('')
  const [step, setStep] = useState('ask')
  const [demo, setDemo] = useState(null)
  const [code, setCode] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const run = async (fn) => { setErr(''); setBusy(true); try { await fn() } catch (ex) { setErr(ex.message) } finally { setBusy(false) } }
  const request = (e) => { e.preventDefault(); run(async () => { const d = await api('/auth/reset/request', { method: 'POST', body: { identifier } }); setDemo(d.demo_code); setStep('confirm') }) }
  const confirm = (e) => { e.preventDefault(); run(async () => { await api('/auth/reset/confirm', { method: 'POST', body: { identifier, code, new_password: pw } }); setDone(true) }) }
  return (
    <div className="card authcard">
      <h2>{t('Reset your password')}</h2>
      {done ? (<>
        <p className="small" style={{ margin: '10px 0' }}>{t('Password changed. Sign in with your new password.')}</p>
        <button className="btn primary block" onClick={onBack}>{t('Back to sign in')}</button>
      </>) : step === 'ask' ? (
        <form className="form" onSubmit={request}>
          <p className="small muted">{t('Enter the email or verified mobile number of your account. We will send a 6-digit code.')}</p>
          <div><label>{t('Email or mobile number')}</label><input value={identifier} onChange={(e) => setIdentifier(e.target.value)} required maxLength={120} autoComplete="username" /></div>
          {err && <p className="small txt-red" role="alert">{err}</p>}
          <button className="btn primary block" disabled={busy}>{busy ? t('Please wait…') : t('Send code')}</button>
        </form>
      ) : (
        <form className="form" onSubmit={confirm}>
          <p className="small muted">{t('If an account matches, a code has been sent.')}</p>
          <DemoCode code={demo} />
          <div><label>{t('6-digit code')}</label><input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" required minLength={6} maxLength={6} /></div>
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
