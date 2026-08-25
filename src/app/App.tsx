import './app.css';

export default function App() {
  return (
    <main className="rebuild-shell">
      <section className="rebuild-card">
        <p className="eyebrow">PARTGRAPH · REBUILD</p>
        <h1>Repair state, remembered.</h1>
        <p className="positioning">
          PartGraph is a stateful AI-assisted repair companion that reconstructs the exact
          vehicle assembly, tracks every part and repair action as you work, and lets you
          stop for days or weeks and resume from the same step, same part, and same fastener.
        </p>
        <div className="status" role="status">
          <span className="status-dot" aria-hidden="true" />
          Block 0 — repository reset
        </div>
        <p className="note">
          Legacy product, collector, generated catalog, and prototype data code have been
          removed. No data collection runs from this application.
        </p>
      </section>
    </main>
  );
}
