import type { ReactNode } from 'react';
import type { GeneralMap, Lane, MapCompany, MapSite, SpecificMap } from './api';
import type { Selection } from './mapStyle';

type Data = { mode: 'specific'; map: SpecificMap } | { mode: 'general'; map: GeneralMap };

const Source = ({ url }: { url: string | null }) =>
  url ? <a href={url} target="_blank" rel="noreferrer">Source ↗</a> : null;

function Row({ label, value }: { label: string; value: ReactNode }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="panel-row">
      <span className="panel-label">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function unmappedReason(c: MapCompany) {
  return c.category?.toLowerCase().includes('fabless') ? 'fabless — no production sites' : 'no sites mapped yet';
}

function SiteDetails({ site }: { site: MapSite }) {
  return (
    <>
      <h3>
        {site.name}
        {site.planned && <span className="status-badge planned">planned</span>}
      </h3>
      <Row label="Operator" value={site.operators.map((o) => o.name).join(' / ') || null} />
      <Row label="Role on map" value={site.role} />
      <Row label="Type" value={site.site_type} />
      <Row label="Status" value={site.status} />
      <Row label="Products" value={site.products} />
      <Row label="Location" value={[site.city, site.country].filter(Boolean).join(', ')} />
      <Row label="Position" value={`approximate (${site.geo_precision ?? 'unknown'} level)`} />
      <Row label="Confidence" value={<span className={`conf conf-${site.confidence}`}>{site.confidence}</span>} />
      {site.events.length > 0 && (
        <div className="panel-events">
          <div className="panel-label">Disruptions</div>
          {site.events.map((ev) => (
            <div key={ev.id} className="panel-event">
              <span className={`event-status status-${ev.status}`}>{ev.status}</span> {ev.name}{' '}
              <Source url={ev.source_url} />
            </div>
          ))}
        </div>
      )}
      <Source url={site.source_url} />
    </>
  );
}

function LaneDetails({ lane, sites }: { lane: Lane; sites: MapSite[] }) {
  const siteName = (id: string) => sites.find((s) => s.id === id)?.name ?? id;
  const chain = [lane.from_company, ...lane.via_companies, lane.to_company].map((c) => c.name).join(' → ');
  return (
    <>
      <h3>{lane.item ?? lane.item_category}</h3>
      <Row label="Companies" value={chain} />
      <Row label="Mode" value={`${lane.mode} (${lane.mode_basis ?? 'basis unknown'})`} />
      <Row label="Transit" value={lane.typical_transit} />
      <Row label="Distance" value={lane.distance_km !== null ? `${Math.round(lane.distance_km).toLocaleString('en-US')} km` : null} />
      <div className="panel-route">
        <div className="panel-label">Route</div>
        <ol>
          <li>{siteName(lane.from_site)}</li>
          {lane.hubs.map((h) => (
            <li key={h.id}>
              {h.name} <span className="muted">· {h.leg_mode} leg</span>
            </li>
          ))}
          <li>{siteName(lane.to_site)}</li>
        </ol>
      </div>
      {lane.chokepoints.length > 0 && (
        <Row
          label="Chokepoints"
          value={lane.chokepoints.map((c) => (
            <span key={c.id} className={c.affected ? 'affected-text' : ''}>
              {c.name}{c.affected ? ' ⚠ affected' : ''}{' '}
            </span>
          ))}
        />
      )}
      <Row label="Confidence" value={<span className={`conf conf-${lane.confidence}`}>{lane.confidence}</span>} />
      <Source url={lane.source_url} />
    </>
  );
}

export default function MapPanel({
  data,
  focusName,
  selection,
  onClear,
}: {
  data: Data;
  focusName: string;
  selection: Selection | null;
  onClear: () => void;
}) {
  let details: ReactNode = null;
  if (selection?.kind === 'site') details = <SiteDetails site={selection.site} />;
  if (selection?.kind === 'lane' && data.mode === 'specific') {
    details = <LaneDetails lane={selection.lane} sites={data.map.sites} />;
  }
  if (selection?.kind === 'country') {
    const c = selection.country;
    details = (
      <>
        <h3>{c.name}</h3>
        {c.roles.map((r) => <Row key={r.role} label={r.role} value={`${r.count} site${r.count === 1 ? '' : 's'}`} />)}
      </>
    );
  }
  if (selection?.kind === 'countryLane') {
    const l = selection.lane;
    details = (
      <>
        <h3>{l.from_country} → {l.to_country}</h3>
        <Row label="Mode" value={l.mode} />
        <Row label="Lanes" value={l.count} />
        <Row label="Chokepoints" value={l.chokepoints.map((c) => `${c.name}${c.affected ? ' ⚠' : ''}`).join(', ') || null} />
      </>
    );
  }

  return (
    <aside className="map-panel">
      {details ? (
        <>
          <button className="panel-back" onClick={onClear}>← Overview</button>
          {details}
        </>
      ) : data.mode === 'specific' ? (
        <>
          <h3>{focusName}</h3>
          <p className="muted">
            {data.map.sites.length} sites · {data.map.lanes.length} lanes. Click a site or lane for details.
          </p>
          {data.map.unmapped.length > 0 && (
            <>
              <div className="panel-label">Not on the map</div>
              <ul className="unmapped">
                {data.map.unmapped.map((c) => (
                  <li key={c.id}>
                    {c.name} <span className="muted">— {unmappedReason(c)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      ) : (
        <>
          <h3>{focusName}</h3>
          <p className="muted">
            Country-level view: {data.map.countries.length} countries, {data.map.lanes.length} lane groups.
            {data.map.unmapped_count > 0 && ` ${data.map.unmapped_count} companies have no mapped sites.`}
          </p>
        </>
      )}
    </aside>
  );
}
