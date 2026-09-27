import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export type Mode = 'specific' | 'general';
export type Confidence = 'high' | 'medium' | 'low';
// Retracted edges never reach the client; historical ones only with include_history.
export type EdgeStatus = 'active' | 'planned' | 'historical';

export interface Vertical {
  id: string;
  name: string;
  populated: boolean;
}

export interface SupplyEdge {
  type: string;
  item: string | null;
  item_category: string | null;
  status: EdgeStatus;
  share_estimate: string | null;
  confidence: Confidence | null;
  source_url: string | null;
}

export interface SpecificUpstream {
  id: string;
  label: string;
  name: string;
  category: string | null;
  edges: SupplyEdge[];
  event_count: number;
  site_count: number;
}

export interface SpecificResponse {
  focus: { id: string; label: string; name: string; category: string | null; event_count: number };
  upstream: SpecificUpstream[];
}

// General mode: the server sends roles and counts only — no names, ids or URLs.
export interface GeneralUpstream {
  role: string;
  supplier_count: number; // suppliers with a current edge in this role
  planned_count: number; // suppliers whose only edges in this role are planned
  historical_count: number; // ... only historical (0 unless include_history)
  confidences: Confidence[];
}

export interface GeneralResponse {
  focus: { label: string; category: string | null };
  upstream: GeneralUpstream[];
}

export interface DisruptionEvent {
  id: string;
  name: string;
  date: string | null;
  status: string;
  severity: string | null;
  description: string | null;
  source_url: string | null;
}

// Levels are cached per (node, mode, context) so jumping back via the breadcrumb is instant.
const cache = new Map<string, Promise<unknown>>();

function cachedGet<T>(path: string, params: Record<string, string | undefined> = {}): Promise<T> {
  const key = `${path}?${JSON.stringify(params)}`;
  if (!cache.has(key)) {
    const request = axios.get<T>(`${API_URL}${path}`, { params }).then((r) => r.data);
    request.catch(() => cache.delete(key)); // don't cache failures
    cache.set(key, request);
  }
  return cache.get(key) as Promise<T>;
}

export const fetchVerticals = () => cachedGet<Vertical[]>('/verticals');

const flag = (on: boolean) => (on ? 'true' : undefined);

export function fetchUpstream(id: string, mode: 'specific', context?: string, history?: boolean): Promise<SpecificResponse>;
export function fetchUpstream(id: string, mode: 'general', context?: string, history?: boolean): Promise<GeneralResponse>;
export function fetchUpstream(id: string, mode: Mode, context?: string, history = false) {
  return cachedGet(`/node/${encodeURIComponent(id)}/upstream`, { mode, context, include_history: flag(history) });
}

// --- Node info (capex, investments, operators) ---

export interface Investment {
  id: string;
  name: string;
  item: string | null;
  amount_usd_bn: string | null;
  date: string | null;
  source_url: string | null;
}

export interface Capex {
  capex_usd_bn: string | null;
  capex_period: string | null;
  capex_as_of: string | null;
  source_url: string | null;
}

export interface SpecificInfo {
  id: string;
  label: string;
  name: string;
  category: string | null;
  country: string | null;
  ticker: string | null;
  description: string | null;
  site_count: number;
  events: DisruptionEvent[];
  capex: (Capex & { vertical_id: string; vertical: string })[];
  investments_out: Investment[];
  investments_in: Investment[];
  operators?: (Capex & { id: string; name: string; category: string | null })[]; // end markets only
}

// General mode: category, country and counts only.
export interface GeneralInfo {
  label: string;
  category: string | null;
  country: string | null;
  site_count: number;
  event_count: number;
  has_capex: boolean;
  investments_out_count: number;
  investments_in_count: number;
  operator_count?: number;
}

export function fetchInfo(id: string, mode: 'specific'): Promise<SpecificInfo>;
export function fetchInfo(id: string, mode: 'general'): Promise<GeneralInfo>;
export function fetchInfo(id: string, mode: Mode) {
  return cachedGet(`/node/${encodeURIComponent(id)}/info`, { mode });
}

export const fetchEvents = (id: string) =>
  cachedGet<DisruptionEvent[]>(`/node/${encodeURIComponent(id)}/events`);

// --- Map mode ---

export type MapRole = 'focus' | 'supplier' | 'material producer' | 'customer' | 'lane endpoint';
export type TransportMode = 'air' | 'sea' | 'road';

export interface CompanyRef {
  id: string;
  name: string;
}

export interface MapCompany extends CompanyRef {
  category: string | null;
  role: Exclude<MapRole, 'lane endpoint'>;
  mapped: boolean;
}

export interface MapSite {
  id: string;
  name: string;
  site_type: string | null;
  status: string | null;
  products: string | null;
  city: string | null;
  country: string;
  lat: number;
  lon: number;
  geo_precision: string | null;
  confidence: Confidence | null;
  source_url: string | null;
  operators: CompanyRef[];
  role: MapRole;
  planned: boolean; // status starts with "planned" / "under construction"
  events: DisruptionEvent[];
}

export interface LaneStop {
  id: string;
  name: string;
  code: string | null;
  hub_type: string;
  kind: 'hub' | 'chokepoint';
  leg_mode: TransportMode | null;
  lat: number;
  lon: number;
  affected: boolean;
}

export interface Lane {
  id: string;
  item: string | null;
  item_category: string | null;
  mode: TransportMode;
  mode_basis: string | null;
  typical_transit: string | null;
  distance_km: number | null;
  confidence: Confidence | null;
  source_url: string | null;
  from_site: string;
  to_site: string;
  from_company: CompanyRef;
  via_companies: CompanyRef[];
  to_company: CompanyRef;
  legs: { seq: number; mode: TransportMode; coords: [number, number][] }[];
  hubs: LaneStop[];
  chokepoints: LaneStop[];
}

export interface SpecificMap {
  focus: { id: string; label: string; name: string; category: string | null };
  companies: MapCompany[];
  sites: MapSite[];
  lanes: Lane[];
  unmapped: MapCompany[];
}

// General mode: country centroids and country-to-country lanes only.
export interface GeneralChokepoint {
  name: string;
  lat: number;
  lon: number;
  affected: boolean;
}

export interface GeneralMap {
  focus: { label: string; category: string | null };
  countries: {
    country: string;
    name: string;
    lat: number;
    lon: number;
    site_count: number;
    roles: { role: MapRole; count: number }[];
  }[];
  lanes: {
    from_country: string;
    to_country: string;
    mode: TransportMode;
    count: number;
    chokepoints: GeneralChokepoint[];
  }[];
  unmapped_count: number;
}

export function fetchMap(id: string, mode: 'specific', context?: string, includeCustomers?: boolean, history?: boolean): Promise<SpecificMap>;
export function fetchMap(id: string, mode: 'general', context?: string, includeCustomers?: boolean, history?: boolean): Promise<GeneralMap>;
export function fetchMap(id: string, mode: Mode, context?: string, includeCustomers = false, history = false) {
  return cachedGet(`/node/${encodeURIComponent(id)}/map`, {
    mode,
    context,
    include_customers: flag(includeCustomers),
    include_history: flag(history),
  });
}
