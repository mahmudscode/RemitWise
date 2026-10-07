import { useEffect, useState } from 'react'
import { api, setToken } from './api'
import { LangToggle } from './ui'
import { t } from './i18n'

const ROLES = [
  ['family', 'Family', 'I receive money from a relative abroad'],
  ['sender', 'Sender abroad', 'I send money home'],
]

export default function Auth({ onAuthed, lang, changeLang }) {
  const [mode, setMode] = useState('login')
  const [cfg, setCfg] = useState({ demo_accounts: [] })
  const [role, setRole] = useState('family')
  const [f, setF] = useState({ name: '', email: '', password: '', invite_code: '', sender_city: '' })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  useEffect(() => { api('/auth/config').then(setCfg).catch((e) => setErr(e.message)) }, [])

  const finish = (d) => { setToken(d.token); onAuthed(d.user) }
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try {
      const d = mode === 'login'
        ? await api('/auth/login', { method: 'POST', body: { email: f.email, password: f.password } })
        : await api('/auth/register', { method: 'POST', body: { role, name: f.name, email: f.email, password: f.password, invite_code: role === 'sender' ? f.invite_code : undefined, sender_city: role === 'family' && f.sender_city ? f.sender_city : undefined } })
      finish(d)
    } catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }
  const demo = async (a) => {
    setErr(''); setBusy(true)
    try { finish(await api('/auth/login', { method: 'POST', body: { email: a.email, password: a.password } })) } catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }
  const roleInfo = ROLES.find((r) => r[0] === role)

  return (
    <div className="authwrap">
      <aside className="authside">
        <div className="brand" style={{ color: '#fff' }}><span className="logo" style={{ background: '#fff', color: 'var(--primary)' }}>R</span>RemitWise</div>
        <div style={{ marginBottom: 6 }}><LangToggle lang={lang} onChange={changeLang} dark /></div>
        <h1>{t('Make every remittance last until the next one.')}</h1>
        <p>{t('An AI planner for families who live on money sent from abroad: it forecasts the next transfer, keeps bills paid on time, warns early about shortfalls, and shares progress with the sender only if the family chooses.')}</p>
        <ul>
          <li>{t('The family always decides. The AI only suggests.')}</li>
          <li>{t('Senders see goal progress only, never spending, unless the family shares more.')}</li>
          <li>{t('Synthetic data only. No real money moves.')}</li>
        </ul>
      </aside>
      <main className="authmain">
        <div className="card authcard">
          <div className="seg" style={{ marginBottom: 16 }}>
            <button className={mode === 'login' ? 'on' : ''} onClick={() => { setMode('login'); setErr('') }}>{t('Sign in')}</button>
            <button className={mode === 'register' ? 'on' : ''} onClick={() => { setMode('register'); setErr('') }}>{t('Create account')}</button>
          </div>

          <form className="form" onSubmit={submit}>
            {mode === 'register' && (<>
              <div><label>{t('I am a…')}</label>
                <div className="roles">{ROLES.map(([k, tt, d]) => (
                  <button type="button" key={k} className={`roletile ${role === k ? 'on' : ''}`} onClick={() => setRole(k)}><b>{t(tt)}</b><small>{t(d)}</small></button>))}</div>
              </div>
              <div><label>{t('Your name')}</label><input value={f.name} onChange={set('name')} required minLength={2} maxLength={60} autoComplete="name" /></div>
            </>)}
            <div><label>{t('Email')}</label><input type="email" value={f.email} onChange={set('email')} required autoComplete="email" /></div>
            <div><label>{t('Password')}{mode === 'register' ? t(' (at least 8 characters)') : ''}</label><input type="password" value={f.password} onChange={set('password')} required minLength={mode === 'register' ? 8 : 1} maxLength={128} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></div>
            {mode === 'register' && role === 'sender' && <div><label>{t('Family invite code')}</label><input value={f.invite_code} onChange={set('invite_code')} placeholder="RW-XXXXXX" required style={{ textTransform: 'uppercase' }} /><small className="muted">{t('Ask your family for the code shown in their app (Goals → Sharing).')}</small></div>}
            {mode === 'register' && role === 'family' && <div><label>{t('Where does your sender work? (optional)')}</label><input value={f.sender_city} onChange={set('sender_city')} placeholder={t('e.g. Dubai')} maxLength={40} /></div>}
            {err && <p className="small txt-red" role="alert">{err}</p>}
            <button className="btn primary block" disabled={busy}>{busy ? t('Please wait…') : mode === 'login' ? t('Sign in') : t('Create {role} account', { role: t(roleInfo[1]).toLowerCase() })}</button>
          </form>

          {mode === 'login' && cfg.demo_accounts.length > 0 && (
            <div style={{ marginTop: 18, borderTop: '1px solid var(--line)', paddingTop: 14 }}>
              <p className="small muted" style={{ marginBottom: 8 }}>{t('Just looking? Try a demo account (synthetic data):')}</p>
              <div className="row wrap">{cfg.demo_accounts.map((a) => <button key={a.email} className="btn sm" disabled={busy} onClick={() => demo(a)}>{a.label}</button>)}</div>
            </div>
          )}
          {mode === 'login' && <p className="tiny muted" style={{ marginTop: 14 }}>{t('Platform staff sign in here too: the app opens the admin console for administrator accounts.')}</p>}
          <p className="tiny muted" style={{ marginTop: 8 }}>{t('By continuing you agree this is a hackathon prototype. No real money, customer data or banking is involved.')}</p>
        </div>
      </main>
    </div>
  )
}
