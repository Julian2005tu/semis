# Task 001 — Load the run 1 seed and build the drill-down navigator

## Goal
Replace the prototype's hand-built sample data with `data/seed/run1/` and turn the graph page into
the left-to-right drill-down described in `CLAUDE.md`, starting from the Datacenter / AI end market.

## Step 0 — Explore before changing anything
- Map the existing backend, frontend, Neo4j setup and tests. Note what already exists from earlier
  work (a chip-type upstream endpoint, a Specific/General toggle, possibly parts of a drill-down).
- Fill in the "Repo layout & commands" section of `CLAUDE.md`.
- Propose a plan and wait for approval.

## Step 1 — Load the seed
- Add a single command to load the seed (e.g. `make seed` or `python -m scripts.seed`) that runs
  `data/seed/run1/load_graph.py` with Neo4j credentials from the project's `.env`.
- Decide with me whether the old sample data should be removed; do not delete it without asking.
- Load with `--reset` and confirm 144 nodes and 408 relationships have
  `seed_run = "run1-datacenter-gpu"`.

## Step 2 — Backend: generic upstream endpoint
`GET /node/{node_id}/upstream?mode=specific|general&context=<ChipType id>`
- Traverse only: `COMPONENT_OF, MAKES, SUPPLIES, FAB_OF, INPUT_TO, PRODUCES, SOURCE_OF`.
- `context` (optional): keep only edges whose `for_chiptypes` is null or contains that id.
- Specific mode returns per upstream node: `id, label, name, category` and per edge:
  `type, item, item_category, share_estimate, confidence, source_url`.
- General mode groups by `item_category` (fallback: the node's `category`) and returns only
  `role`, `supplier_count` and the set of confidence levels. No names, ids or URLs.
- Start from the "Drill-down query" in `data/seed/run1/README.md`. Specific and general queries are
  two separate named constants.
- Add `GET /node/{node_id}/events`: DisruptionEvents with `status` ongoing or upcoming that have an
  `AFFECTS` edge to the node (name, date, status, severity, description, source_url).
- Replace or deprecate the old chip-specific endpoint; keep the frontend working throughout.

## Step 3 — Frontend: drill-down navigator
- Default focus: `vertical_datacenter_ai`. The dropdown becomes "Select End Market" and lists all
  `EndMarketVertical` nodes; `populated = false` ones are disabled with a "coming soon" hint.
- Hierarchical left-to-right layout (dagre): focus on the far right, upstream nodes to its left,
  arrows pointing right into the focus.
- Click an upstream node → it becomes the focus; animate the transition.
- Breadcrumb of the path; clicking a segment jumps back (cache fetched levels client-side).
- Context: the most recent ChipType in the path is sent as `context` on every request below it;
  jumping back via the breadcrumb restores that level's context.
- Specific/General toggle re-fetches the current focus without resetting the path.
- Edge styling by confidence: high solid, medium lighter, low dashed, with a small legend.
- Specific mode: hover tooltip with item, share estimate, confidence and a clickable source link.
- Red badge on nodes with ongoing/upcoming events; clicking opens a side panel listing them.

## Step 4 — Tests (must pass before done)
1. `/node/nvidia/upstream?context=ct_ai_gpu` does **not** include `arm`, `lumentum` or `coherent`;
   without `context` it **does** include `arm`.
2. General-mode responses contain none of the company names in `data/seed/run1/nodes.csv`.
3. `/node/country_US/upstream` returns nothing (geo edges are context, not supply).
4. `/node/vertical_datacenter_ai/upstream` returns exactly the 11 ChipType nodes.
5. Running the seed loader twice leaves node and relationship counts unchanged.
6. Every response is one hop: no returned node is more than one edge away from the focus.

## Done when
All tests pass, I can click from Datacenter / AI → AI GPU → Nvidia → TSMC → ASML → Carl Zeiss SMT in
the UI, and `CLAUDE.md` / `docs/ROADMAP.md` status are updated.
