import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export type Mode = 'specific' | 'general';
export type Confidence = 'high' | 'medium' | 'low';

export interface Vertical {
  id: string;
  name: string;
  populated: boolean;
}

export interface SupplyEdge {
  type: string;
  item: string | null;
  item_category: string | null;
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
  supplier_count: number;
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

export function fetchUpstream(id: string, mode: 'specific', context?: string): Promise<SpecificResponse>;
export function fetchUpstream(id: string, mode: 'general', context?: string): Promise<GeneralResponse>;
export function fetchUpstream(id: string, mode: Mode, context?: string) {
  return cachedGet(`/node/${encodeURIComponent(id)}/upstream`, { mode, context });
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

export function fetchMap(id: string, mode: 'specific', context?: string, includeCustomers?: boolean): Promise<SpecificMap>;
export function fetchMap(id: string, mode: 'general', context?: string, includeCustomers?: boolean): Promise<GeneralMap>;
export function fetchMap(id: string, mode: Mode, context?: string, includeCustomers = false) {
  return cachedGet(`/node/${encodeURIComponent(id)}/map`, {
    mode,
    context,
    include_customers: includeCustomers ? 'true' : undefined,
  });
}
