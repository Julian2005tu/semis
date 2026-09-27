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
