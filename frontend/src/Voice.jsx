import { useEffect, useRef, useState } from 'react'
import { fmtDate, taka } from './api'
import { t, tb } from './i18n'
import { buildAnswer, canSpeak, digest, matchIntent, recognitionCtor, speak, speechLang, stopSpeaking } from './voice'

const F = { t, taka, fmtDate, tb }

const SPEAK_FAIL = {
  unsupported: 'This browser cannot read aloud. You can read the text on screen.',
  no_voice: 'No Bangla voice was found on this device. Install one in the system speech settings, or read the text on screen.',
}

/** 🔊 Read-aloud button. `text` is what is spoken (a function so it is built at click time in the current language). */
export function SpeakButton({ text, lang, label, small, onNote }) {
  const [busy, setBusy] = useState(false)
  if (!canSpeak()) return null  // no speech output on this browser: hide quietly
  const go = async () => {
    if (busy) { stopSpeaking(); setBusy(false); return }
    const r = await speak(typeof text === 'function' ? text() : text, lang)
    if (!r.ok) { onNote?.(t(SPEAK_FAIL[r.reason])); return }
    onNote?.('')
    setBusy(true)
    setTimeout(() => setBusy(false), 4000)
  }
  return <button type="button" className={`btn ${small ? 'sm' : ''} speakbtn`} onClick={go} aria-label={label || t('Read aloud')} title={label || t('Read aloud')}>🔊{!small && <span className="only-desktop"> {label || t('Read aloud')}</span>}</button>
}

/** 🎤 Ask by voice: three fixed questions, answered from the numbers already on the screen. */
export function VoiceAsk({ lang, home, fc }) {
  const Rec = recognitionCtor()
  const [state, setState] = useState('idle')  // idle | listening
  const [heard, setHeard] = useState('')
  const [answer, setAnswer] = useState('')
  const [note, setNote] = useState('')
  const [open, setOpen] = useState(false)
  const rec = useRef(null)
  useEffect(() => () => { try { rec.current?.abort() } catch { /* already stopped */ } }, [])

  const reply = async (said) => {
    setHeard(said)
    const text = buildAnswer(matchIntent(said), { home, fc }, F)
    setAnswer(text)
    const r = await speak(text, lang)
    setNote(r.ok ? '' : t(SPEAK_FAIL[r.reason]))
  }
  const listen = () => {
    if (!Rec) return
    setOpen(true); setNote(''); setHeard(''); setAnswer('')
    const r = new Rec()
    r.lang = speechLang(lang)
    r.interimResults = false
    r.maxAlternatives = 1
    r.onresult = (e) => reply(e.results[0][0].transcript)
    r.onerror = (e) => { setState('idle'); setNote(e.error === 'not-allowed' ? t('Microphone access was blocked. Allow it in the browser settings, or tap a question below.') : t('I could not hear that. Try again, or tap a question below.')) }
    r.onend = () => setState('idle')
    rec.current = r
    setState('listening')
    try { r.start() } catch { setState('idle') }
  }
  const ask = (q) => reply(q)
  const questions = [[t('How much can I spend?'), 'how much can I spend'], [t('When is the next transfer?'), 'when is the next transfer'], [t('Which bills are due?'), 'which bills are due']]
  return (
    <>
      {Rec && <button type="button" className={`btn ${state === 'listening' ? 'primary' : ''}`} onClick={listen} aria-label={t('Ask by voice')} title={t('Ask by voice')}>🎤<span className="only-desktop"> {state === 'listening' ? t('Listening…') : t('Ask')}</span></button>}
      {!Rec && <button type="button" className="btn" onClick={() => setOpen(!open)} title={t('Questions')}>💬<span className="only-desktop"> {t('Ask')}</span></button>}
      {open && (
        <div className="voicepanel card" role="dialog" aria-label={t('Ask by voice')}>
          <div className="row between"><b>{t('Ask a question')}</b><button className="link gray" onClick={() => { stopSpeaking(); setOpen(false) }}>{t('Close')}</button></div>
          <div className="row wrap" style={{ gap: 6, margin: '8px 0' }}>{questions.map(([label, q]) => <button key={q} className="btn sm" onClick={() => ask(label)}>{label}</button>)}</div>
          {heard && <p className="small muted">{t('You asked:')} “{heard}”</p>}
          {answer && <p style={{ margin: '6px 0' }}>{answer}</p>}
          {note && <p className="small txt-amber">{note}</p>}
          {!Rec && <p className="tiny muted">{t('Voice input is not available in this browser, so tap a question instead.')}</p>}
          <p className="tiny muted">{t('Answers come from the numbers on your screen. They are estimates, and you decide.')}</p>
        </div>
      )}
    </>
  )
}

export { digest }
