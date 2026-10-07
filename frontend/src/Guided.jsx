// The judge path (remittance -> allocation -> unusual bill -> warning -> resolution), runnable from the admin sandbox
// and from a bar that floats over the family app, so the presenter never has to leave the story.
export const GUIDED = [
  ['Remittance arrives', 'Triggers a transfer and opens the split pop-up'],
  ['Accept allocation', 'Accepts the suggested split'],
  ['Unusual bill', 'Injects a high electricity bill and moves time until it appears; opens Payments'],
  ['Warning', 'Delays the next transfer and adds a medical emergency; opens Home'],
  ['Resolution', 'Asks the sender to send earlier from the Plan screen'],
]

export function GuidedBar({ guided, go }) {
  return (
    <div className="guidedbar" role="toolbar" aria-label="Guided demo">
      <span className="lbl">Guided demo</span>
      {GUIDED.map(([title], i) => (
        <button key={title} className={guided.last === i + 1 ? 'on' : ''} title={title} onClick={() => guided.run(i + 1)}><b>{i + 1}</b><span className="only-desktop"> {title}</span></button>
      ))}
      <button className="adm" onClick={() => go('admin')}>Admin</button>
    </div>
  )
}
