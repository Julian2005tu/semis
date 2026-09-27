import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
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

// The map libraries are large (~1 MB); load them only when Map is first opened.
const MapView = lazy(() => import('./MapView'));
const MAP_LABELS = ['Company', 'ChipType'];

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
  const [view, setView] = useState<'graph' | 'map'>('graph');
  const [showCustomers, setShowCustomers] = useState(false);
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
  // `view` remembers the user's choice; on a level without a map (e.g. an end market) we just show the
  // graph, and going back to a company shows the map again.
  const mapAvailable = !!focus && MAP_LABELS.includes(focus.label);
  const showMap = view === 'map' && mapAvailable;

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

        <div
          className="control-group segmented"
          role="group"
          aria-label="Graph or map view"
          title={mapAvailable ? undefined : 'Map is available when the focus is a company or chip type'}
        >
          <button className={!showMap ? 'active' : ''} onClick={() => setView('graph')}>Graph</button>
          <button className={showMap ? 'active' : ''} onClick={() => setView('map')} disabled={!mapAvailable}>
            Map
          </button>
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
        {focus && showMap && (
          <Suspense fallback={<div className="graph-frame graph-message">Loading map…</div>}>
            <MapView
              focus={focus}
              mode={mode}
              context={contextFor(path)}
              showCustomers={showCustomers}
              onShowCustomersChange={setShowCustomers}
            />
          </Suspense>
        )}
        {focus && !showMap && (
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
