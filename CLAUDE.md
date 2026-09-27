# Semiconductor Supply-Chain Intelligence Platform

## What we're building
A platform that maps the global semiconductor ecosystem as a knowledge graph: from end markets
(datacenters, automotive, mobile …) back through the chips they need, the companies that make those
chips, their suppliers, equipment, materials and source countries. Later layers add commodity prices,
disruption events and an early-warning system that flags supply-chain risk before it hits.

**Core UX: a left-to-right drill-down navigator.** The focus node sits on the far right; its direct
inputs appear one step to the left; clicking an input makes it the new focus. A breadcrumb shows the
path (e.g. `Datacenter / AI > AI GPU > Nvidia > TSMC`). A **Specific / General** toggle switches
between named companies and generic roles ("Foundry", "HBM", "Photoresist").

Longer-term vision and phase status: `docs/ROADMAP.md`. Current task specs: `docs/tasks/`.

## Stack
- **Neo4j** — the graph (the "knowledge layer" later AI features read from)
- **Python + FastAPI** — API layer and data pipelines
- **React + TypeScript** — frontend; hierarchical left-to-right graph layout (dagre)
- **MapLibre GL + deck.gl** (via `react-map-gl`) — map mode; OpenFreeMap dark basemap (no API key)
- Later: **TimescaleDB** (price time series), **Dagster** (scheduled ingestion),
  **PyOD / ruptures / statsmodels** then **PyTorch Geometric** (early warning)

### Repo layout & commands
- `backend/` — FastAPI app (Python **3.9** venv in `backend/venv`, so no `X | None` syntax).
  `main.py` routes (`/verticals`, `/node/{id}/upstream`, `/node/{id}/map`, `/node/{id}/events`) ·
  `db/neo4j_client.py` all Cypher as named constants · `map_view.py` assembles map responses and the
  country-level General map (incl. country centroids) · `scripts/seed.py` wraps `data/seed/load_seed.py`
  with `.env` credentials · `test_api.py` · `db/postgres_client.py` Phase 3 placeholder, unused.
- `frontend/` — Vite + React 19 + TS. `src/api.ts` (typed fetches, per-level cache) · `App.tsx`
  (path/breadcrumb, context, mode, Graph/Map toggle) · `GraphView.tsx` (React Flow + dagre, LR) ·
  `SupplyNode.tsx` (node, tooltip, event badge, site chip) · `EventsPanel.tsx` · `MapView.tsx` (lazy-loaded
  map, deck.gl layers) · `MapPanel.tsx` (site/lane details, "not on the map") · `mapStyle.ts` (colours,
  basemap). API URL: `VITE_API_URL`, default `http://localhost:8000`.
- `data/seed/` — `load_seed.py` (multi-run loader) + one folder per run (see `data/seed/README.md`).
- **Env** (`backend/.env`): `NEO4J_URI` (bolt://localhost:7687), `NEO4J_USER`, `NEO4J_PASSWORD`.
- **Neo4j:** Neo4j Desktop, local DBMS on bolt://localhost:7687 — start it before anything below.
- **Commands (repo root):** `make seed` (= `python data/seed/load_seed.py run1 run2` with `.env`) /
  `make seed-reset` · `make backend` (uvicorn :8000) · `make frontend` (Vite) · `make test` (graph
  tests skip if Neo4j is down or the seed isn't fully loaded).
- Frontend checks: `cd frontend && npm run build && npm run lint`.

## Graph model
Full schema and field definitions: `data/seed/run1/README.md` and `data/seed/run2/README.md`. The essentials:

- **Labels:** `EndMarketVertical`, `ChipType`, `Company`, `Fab`, `Site`, `Hub`, `Lane`, `RawMaterial`,
  `Country`, `DisruptionEvent`. Sites (incl. run-1 fabs, now also `Site`) carry `lat`, `lon`, `location`.
- **Direction rule:** supply-flow edges point the way goods flow, upstream → downstream.
  "What feeds into X" is always `(X)<-[r]-(upstream)`.
- **Supply-flow types (traverse):** `COMPONENT_OF`, `MAKES`, `SUPPLIES`, `INPUT_TO`, `PRODUCES`, `SOURCE_OF`
- **Context types (never shown as upstream):** `HEADQUARTERED_IN`, `LOCATED_IN`, `SUBSIDIARY_OF`, `AFFECTS`,
  `SITE_OF`, `FROM_SITE`, `TO_SITE`, `VIA`. `FAB_OF` is legacy (run 1) and not traversed.
- **Key edge properties:** `item`, `item_category` (standardised input type, used for General mode),
  `share_estimate`, `confidence` (high / medium / low), `source_url`, `as_of`,
  `for_chiptypes` (`;`-separated ChipType ids the input is for; lanes carry it too)
- **Seed tags:** nodes carry `seed_runs` (list — runs can share a node, e.g. TSMC); relationships carry
  a single `seed_run`.

## Rules that must not break
1. **General mode never sends names, ids or source URLs of companies to the client.** Enforced in the
   API, covered by a test. Hiding fields in the UI does not count. On the map this means country level
   only: no site names or exact site coordinates (country centroids; chokepoints keep their real position).
2. The drill-down endpoint returns **exactly one hop**.
3. Only supply-flow types are traversed; context edges never appear as upstream nodes.
4. When a `context` ChipType is given, only return edges whose `for_chiptypes` is empty or contains it
   (otherwise e.g. Arm shows up as a GPU supplier of Nvidia).
5. Specific-mode and general-mode Cypher live in separate named constants — no dynamic query building
   from user input; always use query parameters.
6. **Cycles exist** (e.g. Nvidia ↔ Coherent). Anything that walks more than one hop keeps a visited set.
7. **Data provenance:** every new supply edge needs `source_url`, `confidence` and `as_of`. Never invent
   market shares or relationships; unverified industry knowledge is marked `low`.
8. **Seed data is append-only by run.** Don't hand-edit files in `data/seed/run*/`; new or corrected data
   goes into a new run folder with its own `SEED_RUN` tag. Runs load through `data/seed/load_seed.py`;
   each run's `nodes.csv` lists every node its relationships touch. `--reset X` only removes run X's data.
9. Ask before anything that deletes data in Neo4j beyond a seed's own `seed_run`.

## How to work here
- For changes touching several files: explore first, propose a plan, wait for approval.
- Add or update tests with every backend change and run them before reporting done.
- Explain non-obvious design decisions in a sentence or two — the builder is learning parts of this stack.
- Prefer simple, readable code over abstractions; this is a solo project that must stay understandable.
- When a milestone lands, update the status in `docs/ROADMAP.md` and the section below.

## Current status (Sept 2026)
- **Task 001 done:** left-to-right drill-down navigator — end-market dropdown, breadcrumb with
  per-level `context`, Specific/General toggle (General enforced server-side), confidence-styled edges,
  source tooltips, disruption badges + events panel, "N sites" chips.
- **Task 002 done:** Graph/Map toggle. Map shows sites of the focus and its suppliers (optionally
  customers), shipment lanes by mode, hubs, chokepoints (pulsing when affected), site/lane panels and a
  "not on the map" list; General mode aggregates to countries. 20 backend tests against the real graph.
- **Data:** run1 + run2 loaded — 262 seed nodes / 675 seed relationships. Run 1: Datacenter/AI vertical,
  GPU chain down to equipment, materials and countries (56 `low` edges). Run 2: 60 sites, 25 hubs,
  40 lanes (16 `low`). Coordinates are city/park level.
- **Next task:** none yet — see `docs/ROADMAP.md`.
