# Roadmap

## Vision
Map every part of the semiconductor ecosystem — all end markets, all chip types, the companies and
fabs that make them, the equipment and materials those depend on, and where those materials come
from — then track prices and events on top of that map so the platform can warn early when a
disruption somewhere upstream is likely to hit a product downstream, including small, indirect effects.

## Decisions made so far (and why)
- **Start from the end of the chain.** Begin at end markets and trace backwards. Demand-side data
  (hyperscaler capex, chip mix) is far easier to source than raw-material data, and it is what
  disruptions ultimately hit.
- **Define every vertical now, populate one at a time.** All seven end markets exist as nodes
  (Datacenter/AI, Automotive, Mobile, PC, Industrial/IoT, Aerospace/Defense, Consumer Electronics).
  Only Datacenter/AI is populated. Verticals share upstream nodes (TSMC, wafer makers, equipment),
  which is exactly how capacity competition between industries shows up — e.g. the 2021 auto shortage.
- **One graph, two views.** Specific vs. General is a query/rendering choice driven by the
  `item_category` / `category` properties, not a second anonymised graph.
- **Neo4j is the knowledge layer for later AI.** A GNN would train on its structure; a GraphRAG chat
  would query it for grounded facts. Both read the same graph.
- **Statistics before deep learning.** Real disruption events are rare (a handful per decade), too few
  to train a neural net early. Anomaly detection and a transparent shock-propagation simulator come first.
- **Every fact carries provenance** (source URL, confidence, as-of date) so warnings can be explained
  and audited.

## Phases

### Phase 1 — Prototype navigator · *in progress*
- [x] Neo4j + FastAPI + React skeleton; chip-type graph page with Specific/General toggle
- [x] Load `data/seed/run1`
- [x] Generic one-hop upstream endpoint with `context` filter and server-enforced General mode
- [x] Left-to-right drill-down UI with breadcrumb, confidence styling, source tooltips, event badges

### Phase 2 — Data coverage · *started (run1 done)*
Each run is a new `data/seed/runN/` folder with its own `seed_run` tag.
- [x] Run 1: Datacenter/AI vertical, GPU chain deep (Sept 2026)
- [ ] Verify the 56 `low` confidence edges from run 1
- [ ] Go vertical: deepen HBM (DRAM fab tools, TSV, hybrid bonding) and EUV (Zeiss/Trumpf sub-suppliers, masks, pellicles)
- [ ] Go horizontal: same depth for server CPU, networking/optics, enterprise SSD
- [ ] Second vertical: Automotive (MCUs, power, analog) — first real cross-vertical overlap query
- [ ] Gaps: China's domestic AI chips (Huawei Ascend, Cambricon, SMIC), server/rack ODMs, datacenter operators and capex

### Phase 3 — Prices and influence
- [ ] TimescaleDB with price series for key materials and chips; link via `RawMaterial.price_series`
- [ ] Scheduled ingestion (Dagster) instead of manual CSV drops
- [ ] Correlation / Granger tests → weighted `PRICE_CORRELATES_WITH` edges
- [ ] Geopolitical layer: export controls, concentration by country

### Phase 4 — Early warning
- [ ] Anomaly detection per series (rolling z-scores, changepoints)
- [ ] Shock-propagation simulator over weighted edges (explainable: shows the path that fired)
- [ ] `risk_score` on nodes, shown as a heat overlay in the same navigator
- [ ] Later, with enough labelled history: GNN (PyTorch Geometric); boosted trees for price forecasts

### Phase 5 — Product
- [ ] Search, saved views, alerts ("tell me when a Tier-2 supplier of ASML shows an anomaly")
- [ ] GraphRAG chat: plain-English questions answered from graph facts
- [ ] Shareable General-mode view that never exposes specific sourcing intelligence
