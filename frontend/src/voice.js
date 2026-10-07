// Read-aloud and simple voice questions (browser APIs only: no paid service, nothing leaves the device for speech output).
// Voice questions map to a few fixed intents answered from data the app already computed. No free-form LLM decisions.

export const speechLang = (lang) => (lang === 'bn' ? 'bn-BD' : 'en-US')
export const canSpeak = () => typeof window !== 'undefined' && 'speechSynthesis' in window
export const recognitionCtor = () => (typeof window === 'undefined' ? null : window.SpeechRecognition || window.webkitSpeechRecognition || null)

const voicesReady = () => new Promise((resolve) => {
  const have = window.speechSynthesis.getVoices()
  if (have.length) return resolve(have)
  const done = () => resolve(window.speechSynthesis.getVoices())
  window.speechSynthesis.addEventListener('voiceschanged', done, { once: true })
  setTimeout(done, 700)  // some browsers never fire the event
})

/** Speak `text`. Resolves { ok } or { ok:false, reason:'unsupported' | 'no_voice' }. */
export async function speak(text, lang) {
  if (!canSpeak()) return { ok: false, reason: 'unsupported' }
  const want = speechLang(lang)
  const voices = await voicesReady()
  const voice = voices.find((v) => v.lang.replace('_', '-').toLowerCase() === want.toLowerCase())
    || voices.find((v) => v.lang.toLowerCase().startsWith(want.slice(0, 2).toLowerCase()))
  if (!voice && lang === 'bn') return { ok: false, reason: 'no_voice' }  // do not read Bangla with an English voice
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = want
  if (voice) u.voice = voice
  u.rate = 0.95
  window.speechSynthesis.speak(u)
  return { ok: true }
}

export const stopSpeaking = () => { if (canSpeak()) window.speechSynthesis.cancel() }

const RULES = [
  ['bills', /(বিল|কিস্তি|বাকি|পরিশোধ|\bbills?\b|\bdue\b|\bemi\b|\bpay\b)/i],
  ['next', /(কবে|পরের|পরবর্তী|ট্রান্সফার|রেমিট্যান্স|আসবে|\bnext\b|\bwhen\b|\btransfer\b|\bremittance\b|\barrive\b|\bmoney come\b)/i],
  ['spend', /(খরচ|কত টাকা|ব্যয়|\bspend\b|\bsafe\b|\bhow much\b|\bafford\b)/i],
]

/** Map what was said to one of: 'spend' | 'next' | 'bills' | null. Works for Bangla and English. */
export function matchIntent(text) {
  const s = (text || '').trim()
  if (!s) return null
  for (const [intent, re] of RULES) if (re.test(s)) return intent
  return null
}

/** Answer an intent from data the app already has. `f` = { t, taka, fmtDate, tb }. Returns plain text (spoken and shown). */
export function buildAnswer(intent, { home, fc }, f) {
  const { t, taka, fmtDate, tb } = f
  if (intent === 'spend') {
    const s = home?.safe
    if (!s) return t('I cannot say yet: there is not enough history for a forecast.')
    return t('You can safely spend about {amt} a day until your next transfer, in about {n} days.', { amt: taka(s.per_day), n: s.days })
  }
  if (intent === 'next') {
    const x = fc?.forecast
    if (!x) return t('I cannot say yet: there is not enough history for a forecast.')
    return t('Your next transfer is expected in {a} to {b} days, about {m} to {n} taka. This is an estimate.', { a: Math.round(x.rem_p10), b: Math.round(x.rem_p90), m: taka(x.amt_p10).replace('৳', ''), n: taka(x.amt_p90).replace('৳', '') })
  }
  if (intent === 'bills') {
    const up = (home?.upcoming || []).slice(0, 3)
    if (!up.length) return t('No bills are due soon.')
    const list = up.map((b) => t('{name} {amt} due {d}', { name: tb(b.name), amt: taka(b.amount ?? b.expected), d: fmtDate(b.due_date) })).join('; ')
    return t('Bills coming up: {list}.', { list })
  }
  return t('Sorry, I can only answer three questions: how much can I spend, when is the next transfer, and which bills are due.')
}

/** What the speaker button reads on Home: safe to spend, next transfer and any warning. */
export function digest({ home, fc }, f) {
  const parts = []
  if (home?.alert) parts.push(f.t('Heads up: you may run short about {n} days before your next transfer.', { n: home.alert.days_short }))
  if (home?.safe) parts.push(buildAnswer('spend', { home, fc }, f))
  if (fc?.forecast) parts.push(buildAnswer('next', { home, fc }, f))
  return parts.join(' ')
}
