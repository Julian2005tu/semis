import { useEffect, useState } from 'react';
import { fetchEvents } from './api';
import type { DisruptionEvent } from './api';
import type { PathEntry } from './App';

export default function EventsPanel({ node, onClose }: { node: PathEntry; onClose: () => void }) {
  const [events, setEvents] = useState<DisruptionEvent[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setEvents(null);
    setError(false);
    fetchEvents(node.id).then(setEvents).catch(() => setError(true));
  }, [node.id]);

  return (
    <aside className="events-panel" aria-label={`Disruptions affecting ${node.name}`}>
      <div className="events-panel-header">
        <h2>Disruptions · {node.name}</h2>
        <button onClick={onClose} aria-label="Close">×</button>
      </div>
      {error && <p>Could not load events.</p>}
      {!events && !error && <p>Loading…</p>}
      {events?.map((ev) => (
        <article key={ev.id} className="event">
          <div className="event-meta">
            <span className={`event-status status-${ev.status}`}>{ev.status}</span>
            {ev.severity && <span className={`event-severity sev-${ev.severity}`}>{ev.severity}</span>}
            {ev.date && <span>{ev.date}</span>}
          </div>
          <h3>{ev.name}</h3>
          {ev.description && <p>{ev.description}</p>}
          {ev.source_url && (
            <a href={ev.source_url} target="_blank" rel="noreferrer">Source ↗</a>
          )}
        </article>
      ))}
    </aside>
  );
}
