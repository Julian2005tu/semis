import { useCallback, useEffect, useState } from 'react';
import GraphView from './GraphView';
import EventsPanel from './EventsPanel';
import { fetchVerticals } from './api';
import type { Mode, Vertical } from './api';
import './App.css';

export interface PathEntry {
  id: string;
  name: string;
  label: string;
}

const DEFAULT_VERTICAL = 'vertical_datacenter_ai';

// The most recent ChipType in the path is the context for everything below it, so e.g.
// Datacenter > AI GPU > Nvidia only shows Nvidia's GPU inputs. Deriving it from the path means
// jumping back via the breadcrumb restores that level's context automatically.
function contextFor(path: PathEntry[]): string | undefined {
  return path.findLast((entry) => entry.label === 'ChipType')?.id;
}

function App() {
  const [verticals, setVerticals] = useState<Vertical[]>([]);
  const [path, setPath] = useState<PathEntry[]>([]);
  const [mode, setMode] = useState<Mode>('specific');
  const [eventsFor, setEventsFor] = useState<PathEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchVerticals()
      .then((vs) => {
        setVerticals(vs);
        const start = vs.find((v) => v.id === DEFAULT_VERTICAL) ?? vs.find((v) => v.populated);
        if (start) setPath([{ id: start.id, name: start.name, label: 'EndMarketVertical' }]);
      })
      .catch(() => setError('Could not reach the API at localhost:8000 — is the backend running?'));
  }, []);

  const focus = path[path.length - 1];

  // Stable callbacks, so re-rendering App (e.g. opening the events panel) doesn't refetch the graph.
  const drillInto = useCallback((entry: PathEntry) => setPath((p) => [...p, entry]), []);
  const showEvents = useCallback((entry: PathEntry) => setEventsFor(entry), []);

  const selectVertical = (id: string) => {
    const v = verticals.find((x) => x.id === id);
    if (v) setPath([{ id: v.id, name: v.name, label: 'EndMarketVertical' }]);
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">Semiconductor Supply Chain</h1>
        <p className="app-subtitle">Click an input to trace it further upstream.</p>
      </header>

      <div className="controls-bar">
        <div className="control-group">
          <label className="control-label" htmlFor="vertical-select">Select End Market</label>
          <select
            id="vertical-select"
            className="chip-select"
            value={path[0]?.id ?? ''}
            onChange={(e) => selectVertical(e.target.value)}
          >
            {verticals.map((v) => (
              <option key={v.id} value={v.id} disabled={!v.populated}>
                {v.name}{v.populated ? '' : ' (coming soon)'}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <span className="control-label">Suppliers:</span>
          <div className="toggle-switch-container">
            <span className={`toggle-label ${mode === 'specific' ? 'active' : ''}`}>Specific</span>
            <label className="switch" aria-label="Toggle Specific or General View">
              <input
                type="checkbox"
                checked={mode === 'general'}
                onChange={(e) => setMode(e.target.checked ? 'general' : 'specific')}
              />
              <span className="slider round"></span>
            </label>
            <span className={`toggle-label ${mode === 'general' ? 'active' : ''}`}>General</span>
          </div>
        </div>
      </div>

      <nav className="breadcrumbs" aria-label="Drill-down path">
        {path.map((entry, i) => (
          // Index in the key: cycles (Nvidia ↔ Coherent) can put the same node in the path twice.
          <span key={`${i}-${entry.id}`} className="crumb">
            <button
              className={i === path.length - 1 ? 'current' : ''}
              onClick={() => setPath(path.slice(0, i + 1))}
            >
              {entry.name}
            </button>
            {i < path.length - 1 && <span className="crumb-sep">›</span>}
          </span>
        ))}
      </nav>

      <main className="main-content">
        {error && <div className="error">{error}</div>}
        {focus && (
          <GraphView
            focus={focus}
            mode={mode}
            context={contextFor(path)}
            onSelect={drillInto}
            onShowEvents={showEvents}
          />
        )}
      </main>

      {eventsFor && <EventsPanel node={eventsFor} onClose={() => setEventsFor(null)} />}
    </div>
  );
}

export default App;
