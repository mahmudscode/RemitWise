import test from 'node:test'
import assert from 'node:assert/strict'
import { matchIntent, speechLang } from './voice.js'

test('English questions map to the three intents', () => {
  assert.equal(matchIntent('How much can I spend today?'), 'spend')
  assert.equal(matchIntent('when is the next transfer'), 'next')
  assert.equal(matchIntent('Which bills are due?'), 'bills')
})

test('Bangla questions map to the three intents', () => {
  assert.equal(matchIntent('কত টাকা খরচ করতে পারি'), 'spend')
  assert.equal(matchIntent('পরের টাকা কবে আসবে'), 'next')
  assert.equal(matchIntent('কোন বিল বাকি'), 'bills')
})

test('bills win over the generic words, unknown questions get no intent', () => {
  assert.equal(matchIntent('when is the next bill due'), 'bills')
  assert.equal(matchIntent('what is the weather'), null)
  assert.equal(matchIntent('   '), null)
  assert.equal(matchIntent(undefined), null)
})

test('speech languages', () => {
  assert.equal(speechLang('bn'), 'bn-BD')
  assert.equal(speechLang('en'), 'en-US')
})

import { buildAnswer, digest } from './voice.js'
const f = { t: (s, v = {}) => s.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? ''), taka: (n) => '৳' + Math.round(n).toLocaleString('en-IN'), fmtDate: (d) => d, tb: (x) => x }
const ctx = {
  home: { safe: { per_day: 640, days: 12 }, upcoming: [{ name: 'Electricity', amount: 2365, due_date: '8 May' }, { name: 'Gas', expected: 831, due_date: '15 May' }], alert: { days_short: 4 } },
  fc: { forecast: { rem_p10: 9.2, rem_p90: 21.4, amt_p10: 18000, amt_p90: 41000 } },
}

test('answers are built only from the data the app already has', () => {
  assert.match(buildAnswer('spend', ctx, f), /৳640 a day.*12 days/)
  assert.match(buildAnswer('next', ctx, f), /9 to 21 days.*18,000 to 41,000.*estimate/)
  assert.match(buildAnswer('bills', ctx, f), /Electricity ৳2,365 due 8 May; Gas ৳831 due 15 May/)
  assert.match(buildAnswer('bills', { home: { upcoming: [] } }, f), /No bills are due soon/)
  assert.match(buildAnswer('spend', {}, f), /not enough history/)
  assert.match(buildAnswer(null, ctx, f), /only answer three questions/)
})

test('the read-aloud digest leads with a warning, then spend and next transfer', () => {
  const d = digest(ctx, f)
  assert.ok(d.startsWith('Heads up: you may run short about 4 days'))
  assert.match(d, /safely spend/)
  assert.match(d, /next transfer is expected/)
  assert.equal(digest({}, f), '')
})
