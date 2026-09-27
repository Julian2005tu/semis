# Run 2 — Production sites, logistics hubs and shipment lanes

**Seed run tag:** `run2-sites-logistics` · **As of:** September 2026 · builds on run 1 (load run 1 first)

Adds the physical layer under the GPU chain for the map mode: where things are made and how they
travel between those places.

| New | Count | Notes |
|---|---|---|
| `Site` nodes | 47 new + the 13 run-1 `Fab` nodes (now also labelled `Site`) = **60 sites with coordinates** | fabs, packaging sites, substrate/material plants, equipment makers, mines, gas plants, server assembly |
| `Lane` nodes | **40** | 19 air, 15 road, 6 sea; each with legs, geometry, hubs and computed chokepoints |
| `Hub` nodes | **25** | 10 airports, 7 seaports, 8 maritime chokepoints |
| `Company` nodes | 3 | Foxconn and Wistron (Nvidia's rack/superchip assemblers), QatarEnergy (helium) |
| `Country` nodes | 3 | Mexico, India, Malaysia |

## Schema additions

**Nodes**
- `Site` — `site_type`, `status`, `products`, `city`, `lat`, `lon`, `location` (Neo4j point, set by the
  loader), `geo_precision` (`park` / `city` / `region`), `confidence`. Front-end fabs also carry `Fab`.
- `Hub` — `hub_type` (`airport` / `seaport` / `chokepoint`), `code` (IATA or UN/LOCODE), `lat`, `lon`.
- `Lane` — one typical physical flow between two sites: `item`, `item_category`, `mode` (main leg:
  `air` / `sea` / `road`), `mode_basis` (`reported` vs `typical practice (inferred)`), `typical_transit`,
  `from_company`, `to_company`, `via_companies` (distributors in between, `;`-separated),
  `for_chiptypes`, `distance_km`, `chokepoints` (`;`-separated Hub ids), `geometry` (JSON: list of legs
  `{seq, mode, coords: [[lon, lat], …]}`), `confidence`, `source_url`.

**Relationships (all context — never traversed by the drill-down)**
- `(Site)-[:SITE_OF]->(Company)` — who operates the site (a JV site points to both partners).
  Also added for the 13 run-1 fabs; `FAB_OF` from run 1 is now legacy.
- `(Site)-[:LOCATED_IN]->(Country)`
- `(Lane)-[:FROM_SITE]->(Site)`, `(Lane)-[:TO_SITE]->(Site)`
- `(Lane)-[:VIA {seq, kind, leg_mode}]->(Hub)` — airports/ports in order, then chokepoints.
- `(DisruptionEvent)-[:AFFECTS]->(Hub | Site)` — the helium event now also affects the Strait of Hormuz
  and Ras Laffan.

New commercial edges: Nvidia → Foxconn and Nvidia → Wistron (`SUPPLIES`, downstream customers),
QatarEnergy → Air Liquide (helium), QatarEnergy `PRODUCES` Helium.

`routes.geojson` holds the same lane geometry as a GeoJSON FeatureCollection (one LineString per leg)
for quick inspection in any GeoJSON viewer.

## How the geometry was made
- **Road legs:** straight lines between points — illustrative, not a road route.
- **Air legs:** great-circle arcs between airports. Real Europe–Asia freighters avoid Russian airspace
  (and in 2026 parts of the Middle East), so actual paths are longer.
- **Sea legs:** computed with the `searoute` Python package on its marine network. Chokepoints were
  detected by distance from the route. Europe–Asia routes default to Suez; they may divert via the
  Cape of Good Hope when the Red Sea is avoided.

## Confidence — read this before trusting the map
- **Coordinates are approximate** (city or industrial-park level, `geo_note` on every site), not
  surveyed building locations.
- **Sites:** 13 high, 13 medium, 21 low among the new ones. Low = well-known industry knowledge not
  verified in this run.
- **Lanes:** 4 high, 20 medium, 16 low. Most lanes describe *typical* movement (`mode_basis`), not a
  disclosed contract. What is reported: EUV tools fly in (≈40 containers, 3 Boeing 747 freighters,
  20 trucks per system); HBM goes to TSMC for CoWoS integration; all TSMC chips, including
  Arizona-made ones, are packaged in Taiwan today; Qatari helium moves by sea in ISO containers
  through Hormuz; AI hardware leaves Taiwan mainly by air through Taoyuan.
- **Destinations inside TSMC are simplified.** TSMC does not disclose which advanced-packaging site
  receives which inputs. Imports are drawn to AP6 Zhunan (nearest to Taoyuan airport), with AP7 Chiayi
  and AP8 Tainan fed from the Tainan fab.

## Known gaps
Where TSMC's N12 HBM base dies are fabbed; Nvidia's Taiwan-based rack assemblers (most output is
still in Taiwan — Fort Worth is ~5%); equipment makers other than ASML's chain (AMAT, Lam, TEL, KLA
sites); photoresist and wafer routes beyond one example each; Amkor/ASE lanes for outsourced CoWoS.

## Main sources
TSMC sites: [TrendForce AP7 & Arizona](https://www.trendforce.com/news/2025/12/04/news-tsmc-speeds-advanced-packaging-ap7-targets-2026-output-arizona-p6-eyed-for-u-s-packaging-hub/),
[AI in Asia on CoWoS sites](https://aiinasia.com/greater-china/tsmc-cowos-ai-packaging-capacity-taiwan-supply-chain-2026),
[Tech Times on Longtan](https://www.techtimes.com/articles/323679/20260809/tsmc-revives-longtan-14nm-fabs-cowos-hub-both-sell-out-globally.htm) ·
Memory: [TrendForce on SK hynix P&T7](https://www.trendforce.com/news/2026/01/13/news-sk-hynix-to-build-cheongju-advanced-packaging-fab-boosting-hbm-output-by-2027/),
[TrendForce on Samsung Onyang](https://www.trendforce.com/news/2026/08/20/news-samsung-to-break-ground-on-krw-6t-onyang-hbm-fab-in-sept-p5-eyes-triple-fab-shift-as-expansion-accelerates/),
[BigGo on Micron sites](https://finance.biggo.com/news/h0Jk9ZwB5edQG9E457Lh) ·
Substrates/ABF: [Ibiden investment notice](https://www.ibiden.com/company/2026/02/notice-regarding-capital-investment-plan-for-high-performance-ic-package-substrates.html),
[Ajinomoto plant-site release](https://www.ajinomoto.com/cms_wp_ajnmt_global/wp-content/uploads/pdf/2026_05_07_02E.pdf) ·
Assembly: [Nvidia blog on Wistron Fort Worth](https://blogs.nvidia.com/blog/wistron-manufacturing-texas/),
[TrendForce: Fort Worth ~5% of output](https://www.trendforce.com/news/2026/07/22/news-wistron-produces-first-u-s-made-gb300-baseboard-d1-factory-represents-just-5-of-nvidias-output/),
[Mexico News Daily on Foxconn Guadalajara](https://mexiconewsdaily.com/business/foxconn-nvidia-mexico-superchip-plant/) ·
Logistics: [Intel on EUV delivery](https://download.intel.com/newsroom/archive/2025/en-us-2021-12-21-euv-the-most-precise-complex-machine-at-intel.pdf),
[CNBC on Taiwan packaging](https://www.cnbc.com/2026/04/08/tsmc-nvidia-advanced-packaging-intel.html),
[Value Chain Asia on helium and Hormuz](https://valuechainasia.com/articles/technology/tsmc-helium-shortage-semiconductor-supply-chain-2026),
[The Elec on Korean helium contracts](https://www.thelec.net/news/articleView.html?idxno=6422),
[STAT Times on Taiwan AI air cargo](https://www.stattimes.com/amp/air-cargo/dimerco-taiwan-ai-cargo-demand-keeps-asia-pacific-airfreight-tight-1359680).
Every site and lane row carries its own `source_url`.
