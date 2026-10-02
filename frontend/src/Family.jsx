import { useState } from 'react'
import Home from './Home.jsx'
import Payments from './Payments.jsx'
import Plan from './Plan.jsx'
import Goals from './Goals.jsx'
import Insights from './Insights.jsx'
import RemittanceModal from './RemittanceModal.jsx'

const TABS = [['home', '🏠', 'Home'], ['payments', '💳', 'Payments'], ['plan', '📈', 'Plan'], ['goals', '🎯', 'Goals'], ['insights', '💡', 'Insights']]

export default function Family(props) {
  const { hid, state, role, user, tick, lang, act } = props
  const [tab, setTab] = useState(() => { const t = location.hash.slice(1).split('/')[1]; return TABS.some((x) => x[0] === t) ? t : 'home' })
  const [dismissed, setDismissed] = useState(null)
  const H = { role, user }
  const common = { hid, state, tick, lang, H, act, onNav: setTab }
  const showModal = state.pending && dismissed !== state.pending.seq

  return (
    <div className="phone">
      <div className="phone-body">
        {tab === 'home' && <Home {...common} />}
        {tab === 'payments' && <Payments {...common} />}
        {tab === 'plan' && <Plan {...common} />}
        {tab === 'goals' && <Goals {...common} />}
        {tab === 'insights' && <Insights {...common} />}
      </div>
      {state.pending && !showModal && <button className="fab" onClick={() => setDismissed(null)}>💸 Remittance arrived: decide</button>}
      <nav className="bottomnav">
        {TABS.map(([k, ico, label]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}><span>{ico}</span>{label}</button>)}
      </nav>
      {showModal && <RemittanceModal {...common} person={props.person} onClose={() => setDismissed(state.pending?.seq ?? null)} />}
    </div>
  )
}
