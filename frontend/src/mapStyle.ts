import type { GeneralMap, Lane, MapRole, MapSite, TransportMode } from './api';

// Free vector basemap, no API key (https://openfreemap.org). MapLibre shows the required
// "© OpenMapTiles Data from OpenStreetMap" attribution from the style automatically.
export const MAP_STYLE = 'https://tiles.openfreemap.org/styles/dark';

export type RGB = [number, number, number];

export const ROLE_COLORS: Record<MapRole, RGB> = {
  focus: [59, 130, 246],
  supplier: [167, 139, 250],
  'material producer': [251, 146, 60],
  customer: [74, 222, 128],
  'lane endpoint': [148, 163, 184],
};

export const MODE_COLORS: Record<TransportMode, RGB> = {
  air: [56, 189, 248],
  sea: [45, 212, 191],
  road: [250, 204, 21],
};

export const rgb = (c: RGB) => `rgb(${c.join(',')})`;

export type GeneralCountry = GeneralMap['countries'][number];
export type GeneralLane = GeneralMap['lanes'][number];

// What the side panel shows details for.
export type Selection =
  | { kind: 'site'; site: MapSite }
  | { kind: 'lane'; lane: Lane }
  | { kind: 'country'; country: GeneralCountry }
  | { kind: 'countryLane'; lane: GeneralLane };
