import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { fetchInfo } from './api';
import type { GeneralInfo, Investment, Mode, SpecificInfo } from './api';
import type { PathEntry } from './App';

type Info = { mode: 'specific'; info: SpecificInfo } | { mode: 'general'; info: GeneralInfo };

const Source = ({ url }: { url: string | null }) =>
  url ? <a href={url} target="_blank" rel="noreferrer">↗</a> : null;

function Fact({ label, value }: { label: string; value: ReactNode }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="panel-row">
      <span className="panel-label">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Investments({ title, rows }: { title: string; rows: Investment[] }) {
  if (!rows.length) return null;
  return (
    <section className="info-section">
      <h3>{title}</h3>
      <ul className="info-list">
        {rows.map((r) => (
          <li key={`${r.id}-${r.item}`}>
            <strong>{r.name}</strong>
            {r.amount_usd_bn && <> · ${r.amount_usd_bn}bn</>}
            {r.date && <span className="muted"> · {r.date}</span>} <Source url={r.source_url} />
            {r.item && <div className="muted">{r.item}</div>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function SpecificDetails({ info }: { info: SpecificInfo }) {
  return (
    <>
      <Fact label="Category" value={info.category} />
      <Fact label="Country" value={info.country} />
      <Fact label="Ticker" value={info.ticker} />
      <Fact label="Sites" value={info.site_count || null} />
      {info.description && <p className="info-description">{info.description}</p>}

      {info.operators && info.operators.length > 0 && (
        <section className="info-section">
          <h3>Who is buying</h3>
          <p className="muted">AI-infrastructure capex, largest first (as reported, not normalised).</p>
          <table className="info-table">
            <thead>
              <tr><th>Operator</th><th>Capex (US$ bn)</th><th>Period</th><th /></tr>
            </thead>
            <tbody>
              {info.operators.map((o) => (
                <tr key={o.id}>
                  <td>{o.name}</td>
                  <td>{o.capex_usd_bn ?? <span className="muted">not disclosed</span>}</td>
                  <td className="muted">{o.capex_period}</td>
                  <td><Source url={o.source_url} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {info.capex.length > 0 && (
        <section className="info-section">
          <h3>Capex</h3>
          {info.capex.map((c) => (
            <div key={c.vertical_id} className="panel-row">
              <span className="panel-label">{c.vertical}</span>
              <span>
                {c.capex_usd_bn ? `$${c.capex_usd_bn}bn` : 'not disclosed'}
                {c.capex_period && <span className="muted"> · {c.capex_period}</span>} <Source url={c.source_url} />
              </span>
            </div>
          ))}
        </section>
      )}

      <Investments title="Investments made" rows={info.investments_out} />
      <Investments title="Investments received" rows={info.investments_in} />

      {info.events.length > 0 && (
        <section className="info-section">
          <h3>Active disruptions</h3>
          <ul className="info-list">
            {info.events.map((ev) => (
              <li key={ev.id}>
                <span className={`event-status status-${ev.status}`}>{ev.status}</span> {ev.name}{' '}
                <Source url={ev.source_url} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

// General mode: the server sends category, country and counts only.
function GeneralDetails({ info }: { info: GeneralInfo }) {
  return (
    <>
      <Fact label="Category" value={info.category} />
      <Fact label="Country" value={info.country} />
      <Fact label="Sites" value={info.site_count} />
      <Fact label="Active disruptions" value={info.event_count} />
      <Fact label="Investments made" value={info.investments_out_count} />
      <Fact label="Investments received" value={info.investments_in_count} />
      {info.operator_count !== undefined && <Fact label="Operators" value={info.operator_count} />}
      <p className="muted">General mode shows aggregates only.</p>
    </>
  );
}

export default function InfoPanel({ node, mode, onClose }: { node: PathEntry; mode: Mode; onClose: () => void }) {
  const [data, setData] = useState<Info | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setData(null);
    setError(false);
    const request =
      mode === 'specific'
        ? fetchInfo(node.id, 'specific').then((info) => ({ mode: 'specific' as const, info }))
        : fetchInfo(node.id, 'general').then((info) => ({ mode: 'general' as const, info }));
    request.then(setData).catch(() => setError(true));
  }, [node.id, mode]);

  return (
    <aside className="events-panel info-panel" aria-label={`Details for ${node.name}`}>
      <div className="events-panel-header">
        <h2>{node.name}</h2>
        <button onClick={onClose} aria-label="Close">×</button>
      </div>
      {error && <p>Could not load details.</p>}
      {!data && !error && <p>Loading…</p>}
      {data?.mode === 'specific' && <SpecificDetails info={data.info} />}
      {data?.mode === 'general' && <GeneralDetails info={data.info} />}
    </aside>
  );
}
