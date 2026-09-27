import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Map as MapGL, Marker, NavigationControl, useControl } from 'react-map-gl/maplibre';
import type { MapRef } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { setWorkerUrl } from 'maplibre-gl';
// MapLibre finds its tile worker relative to its own file, which breaks once Vite bundles it. Let Vite
// bundle the worker (with its shared chunk) and hand MapLibre the resulting URL instead.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { MapboxOverlay } from '@deck.gl/mapbox';
import type { MapboxOverlayProps } from '@deck.gl/mapbox';
import { ArcLayer, PathLayer, ScatterplotLayer } from '@deck.gl/layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import type { PathStyleExtensionProps } from '@deck.gl/extensions';
import type { PickingInfo } from '@deck.gl/core';
import { fetchMap } from './api';
import type { GeneralMap, Lane, MapRole, MapSite, Mode, SpecificMap, TransportMode } from './api';
import type { PathEntry } from './App';
import MapPanel from './MapPanel';
import { MAP_STYLE, MODE_COLORS, ROLE_COLORS, rgb } from './mapStyle';
import type { GeneralCountry, GeneralLane, Selection } from './mapStyle';

setWorkerUrl(maplibreWorkerUrl);

// deck.gl draws on top of the MapLibre map through this control.
function DeckOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props));
  overlay.setProps(props);
  return null;
}

interface LegDatum {
  lane: Lane;
  mode: TransportMode;
  path: [number, number][];
}

const dashed = new PathStyleExtension({ dash: true });

// Longitude frame. When the shown places span less of the globe across the Pacific than across the
// Atlantic (Taiwan + Arizona, say), move the western hemisphere by +360° so the view centres on the
// Pacific and transpacific lanes take the short way. MapLibre draws world copies, so lon > 180 is fine.
interface LonFrame {
  lon: (lon: number) => number;
  pacific: boolean;
}

function lonFrame(lons: number[]): LonFrame {
  const span = (xs: number[]) => (xs.length ? Math.max(...xs) - Math.min(...xs) : 0);
  const shifted = (l: number) => (l < 0 ? l + 360 : l);
  return span(lons.map(shifted)) < span(lons) ? { lon: shifted, pacific: true } : { lon: (l) => l, pacific: false };
}

// Applies the frame to a leg and removes any remaining ±360° jumps, so each leg is one continuous line.
function framePath(coords: [number, number][], frame: LonFrame): [number, number][] {
  const out: [number, number][] = [];
  for (const [lon, lat] of coords) {
    let x = frame.lon(lon);
    const prev = out[out.length - 1];
    if (prev) x += 360 * Math.round((prev[0] - x) / 360);
    out.push([x, lat]);
  }
  return out;
}

function specificLayers(data: SpecificMap, frame: LonFrame, select: (s: Selection) => void) {
  const legs: LegDatum[] = data.lanes.flatMap((lane) =>
    lane.legs.map((leg) => ({ lane, mode: leg.mode, path: framePath(leg.coords, frame) })),
  );
  const hubs = [...new Map(
    data.lanes.flatMap((l) => l.hubs).map((h) => [h.id, h] as const),
  ).values()];

  return [
    new PathLayer<LegDatum, PathStyleExtensionProps<LegDatum>>({
      id: 'lanes',
      data: legs,
      getPath: (d) => d.path,
      getColor: (d) => MODE_COLORS[d.mode],
      getWidth: 2.5,
      widthUnits: 'pixels',
      // Same convention as the graph: low-confidence lanes are dashed.
      getDashArray: (d) => (d.lane.confidence === 'low' ? [4, 3] : [0, 0]),
      dashJustified: true,
      extensions: [dashed],
      pickable: true,
      onClick: ({ object }) => object && select({ kind: 'lane', lane: object.lane }),
    }),
    new ScatterplotLayer({
      id: 'hubs',
      data: hubs,
      getPosition: (h) => [frame.lon(h.lon), h.lat],
      getRadius: 3,
      radiusUnits: 'pixels',
      getFillColor: [226, 232, 240],
      pickable: true,
    }),
    new ScatterplotLayer<MapSite>({
      id: 'sites',
      data: data.sites,
      getPosition: (s) => [frame.lon(s.lon), s.lat],
      getRadius: (s) => (s.role === 'focus' ? 9 : 6),
      radiusUnits: 'pixels',
      getFillColor: (s) => ROLE_COLORS[s.role],
      stroked: true,
      lineWidthUnits: 'pixels',
      getLineWidth: (s) => (s.events.length ? 2.5 : 1),
      getLineColor: (s) => (s.events.length ? [220, 38, 38] : [15, 23, 42]),
      pickable: true,
      onClick: ({ object }) => object && select({ kind: 'site', site: object }),
    }),
  ];
}

function generalLayers(data: GeneralMap, frame: LonFrame, select: (s: Selection) => void) {
  const byCode = Object.fromEntries(data.countries.map((c) => [c.country, { ...c, lon: frame.lon(c.lon) }]));
  // Lanes inside one country have no length at country level; they count in the country bubble instead.
  const lanes = data.lanes.filter((l) => l.from_country !== l.to_country);
  return [
    new ArcLayer<GeneralLane>({
      id: 'country-lanes',
      data: lanes,
      getSourcePosition: (l) => [byCode[l.from_country].lon, byCode[l.from_country].lat],
      getTargetPosition: (l) => [byCode[l.to_country].lon, byCode[l.to_country].lat],
      getSourceColor: (l) => MODE_COLORS[l.mode],
      getTargetColor: (l) => MODE_COLORS[l.mode],
      getWidth: (l) => 1.5 + l.count,
      widthUnits: 'pixels',
      getHeight: 0.4,
      pickable: true,
      onClick: ({ object }) => object && select({ kind: 'countryLane', lane: object }),
    }),
    new ScatterplotLayer<GeneralCountry>({
      id: 'countries',
      data: data.countries,
      getPosition: (c) => [frame.lon(c.lon), c.lat],
      getRadius: (c) => 6 + 4 * Math.sqrt(c.site_count),
      radiusUnits: 'pixels',
      getFillColor: (c) => [...ROLE_COLORS[c.roles.some((r) => r.role === 'focus') ? 'focus' : 'supplier'], 200],
      stroked: true,
      lineWidthUnits: 'pixels',
      getLineWidth: 1,
      getLineColor: [15, 23, 42],
      pickable: true,
      onClick: ({ object }) => object && select({ kind: 'country', country: object }),
    }),
  ];
}

function tooltip({ object, layer }: PickingInfo) {
  if (!object || !layer) return null;
  switch (layer.id) {
    case 'sites':
      return `${object.name}\n${object.operators.map((o: { name: string }) => o.name).join(' / ')}`;
    case 'hubs':
      return object.name;
    case 'lanes':
      return `${object.lane.item ?? object.lane.item_category} · ${object.mode}`;
    case 'countries':
      return `${object.name}: ${object.site_count} site${object.site_count === 1 ? '' : 's'}`;
    case 'country-lanes':
      return `${object.from_country} → ${object.to_country} · ${object.mode} · ${object.count} lane${object.count === 1 ? '' : 's'}`;
  }
  return null;
}

// Positions to fit the view to: sites in specific mode, country bubbles in general mode.
function boundsOf(points: { lat: number; lon: number }[], frame: LonFrame): [[number, number], [number, number]] | null {
  if (!points.length) return null;
  const lons = points.map((p) => frame.lon(p.lon));
  const lats = points.map((p) => p.lat);
  return [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
}

export default function MapView({
  focus,
  mode,
  context,
  showCustomers,
  onShowCustomersChange,
}: {
  focus: PathEntry;
  mode: Mode;
  context?: string;
  showCustomers: boolean;
  onShowCustomersChange: (on: boolean) => void;
}) {
  const mapRef = useRef<MapRef>(null);
  const [data, setData] = useState<{ mode: 'specific'; map: SpecificMap } | { mode: 'general'; map: GeneralMap } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    setSelection(null);
    const request =
      mode === 'specific'
        ? fetchMap(focus.id, 'specific', context, showCustomers).then((map) => ({ mode: 'specific' as const, map }))
        : fetchMap(focus.id, 'general', context, showCustomers).then((map) => ({ mode: 'general' as const, map }));
    request
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setError('Could not load the map for this node.'));
    return () => {
      cancelled = true;
    };
  }, [focus.id, mode, context, showCustomers]);

  const places = useMemo(
    () => (!data ? [] : data.mode === 'specific' ? data.map.sites : data.map.countries),
    [data],
  );
  const frame = useMemo(() => lonFrame(places.map((p) => p.lon)), [places]);
  const bounds = useMemo(() => boundsOf(places, frame), [places, frame]);

  const layers = useMemo(() => {
    if (!data) return [];
    return data.mode === 'specific'
      ? specificLayers(data.map, frame, setSelection)
      : generalLayers(data.map, frame, setSelection);
  }, [data, frame]);

  // Chokepoints are HTML markers so "affected" can pulse with plain CSS.
  const chokepoints = useMemo(() => {
    if (!data) return [];
    const all = data.mode === 'specific'
      ? data.map.lanes.flatMap((l) => l.chokepoints).map((c) => ({ key: c.id, ...c }))
      : data.map.lanes.flatMap((l) => l.chokepoints).map((c) => ({ key: c.name, ...c }));
    return [...new Map(all.map((c) => [c.key, c] as const)).values()];
  }, [data]);

  // Runs when new data arrives, and on map load in case the data came first.
  const fitToData = useCallback(() => {
    // Extra padding on the right and bottom keeps sites clear of the side panel and legend.
    const padding = { top: 60, left: 50, right: 340, bottom: 110 };
    if (bounds && mapRef.current) mapRef.current.fitBounds(bounds, { padding, maxZoom: 7, duration: 800 });
  }, [bounds]);

  useEffect(fitToData, [fitToData]);

  return (
    <div className="graph-frame map-frame">
      <MapGL
        ref={mapRef}
        mapStyle={MAP_STYLE}
        initialViewState={{ longitude: 60, latitude: 25, zoom: 1.3 }}
        onLoad={fitToData}
        style={{ position: 'absolute', inset: 0 }}
      >
        <NavigationControl position="bottom-right" showCompass={false} />
        <DeckOverlay layers={layers} getTooltip={tooltip} />
        {chokepoints.map((c) => (
          <Marker key={c.key} longitude={frame.lon(c.lon)} latitude={c.lat} anchor="center">
            <div
              className={`chokepoint ${c.affected ? 'affected' : ''}`}
              title={`${c.name}${c.affected ? ' — affected by an ongoing disruption' : ''}`}
            >
              !
            </div>
          </Marker>
        ))}
      </MapGL>

      <div className="map-toolbar">
        <label className="map-switch">
          <input type="checkbox" checked={showCustomers} onChange={(e) => onShowCustomersChange(e.target.checked)} />
          Show customers
        </label>
      </div>

      {error && <div className="graph-message map-message">{error}</div>}
      {!data && !error && <div className="graph-message map-message">Loading map…</div>}

      {data && (
        <MapPanel
          data={data}
          focusName={focus.name}
          selection={selection}
          onClear={() => setSelection(null)}
        />
      )}
      <MapLegend />
    </div>
  );
}

function MapLegend() {
  return (
    <div className="legend map-legend">
      {(Object.keys(ROLE_COLORS) as MapRole[]).map((role) => (
        <span key={role}><i className="dot" style={{ background: rgb(ROLE_COLORS[role]) }} />{role}</span>
      ))}
      {(Object.keys(MODE_COLORS) as TransportMode[]).map((m) => (
        <span key={m}><i className="bar" style={{ background: rgb(MODE_COLORS[m]) }} />{m}</span>
      ))}
      <span><i className="bar dashed" />low confidence</span>
      <span><i className="chokepoint mini">!</i>chokepoint</span>
      <span><i className="chokepoint mini affected">!</i>affected</span>
    </div>
  );
}
