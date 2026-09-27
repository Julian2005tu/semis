# Task 003 — Load run 3 (depth pass) and support its new data features

## Goal
Load `data/seed/run3/` and make the app handle what it introduces:
- a new loader that lets later runs update earlier edges;
- a `status` on relationships (planned / historical / retracted);
- two context relationship types, `OPERATES_IN` (operator capex) and `INVESTS_IN` (investments);
- a 12th datacenter chip type (BMC);
- more parallel edges between the same two nodes.

Read `data/seed/README.md` and `data/seed/run3/README.md` first.

## Step 0 — Explore and plan
- Check how tasks 001 and 002 were implemented (upstream and map endpoints, seed command, tests).
- Propose a plan and wait for approval.

## Step 1 — Loader
- `data/seed/load_seed.py` has been replaced (it came with this kit). What changed:
  - relationships now carry `seed_runs` (every run that wrote them) in addition to `seed_run` (creator);
  - `--rebuild` wipes all seed data and loads every `runN` folder in ascending order;
  - `--dry-run` without arguments validates all runs.
- Make the project's seed command `python data/seed/load_seed.py --rebuild`.
- Verify after a rebuild: seed nodes = **374**, seed relationships = **979**.
- Keep the task-002 loader test working; adjust it only where the new semantics require it.
  Loading run1 + run2 must still give 262 / 675, and `--reset run2` must give 144 / 408.
- New loader test: after a rebuild, `--reset run3` returns to 262 / 675. The edge
  `advantest -SUPPLIES-> nvidia` still exists and keeps `seed_run = "run1-datacenter-gpu"`
  (its confidence stays `high` until the next rebuild — that is documented behaviour).

## Step 2 — Relationship `status`
Values: absent / `active`, `planned`, `historical`, `retracted`.
- **Drill-down and map:** exclude `historical` and `retracted` by default. Include `planned`, but
  return `status` so the UI can mark it.
- **API:** add `include_history=true` to the upstream and map endpoints to also return `historical`
  edges (still never `retracted`).
- **UI:** planned edges are drawn dotted with a small "planned" badge in tooltips and panels, and the
  legend gets a "planned" entry. Add a "Show history" toggle (off by default) that also includes
  `historical` edges, greyed out. `retracted` edges are never shown.
- General mode: `planned` counts are reported separately, e.g. `{role, supplier_count, planned_count}`.
- Map: lanes and sites have no status yet. Treat a Site whose `status` starts with "planned" or
  "under construction" as planned (dotted outline).

## Step 3 — Context types `OPERATES_IN` and `INVESTS_IN`
Both are context only and are never traversed by the drill-down or map.
- New endpoint `GET /node/{node_id}/info?mode=specific|general`. It returns the node's name,
  category, country, ticker, description, `site_count`, active events, and:
  - `capex`: for a Company with `OPERATES_IN` — `capex_usd_bn`, `capex_period`, `capex_as_of`,
    source.
  - `investments_out` / `investments_in`: `INVESTS_IN` edges with counterparty name, item,
    `amount_usd_bn`, date, source.
  - For an `EndMarketVertical`: `operators`, the companies that `OPERATES_IN` it with their capex,
    sorted by capex (parse the first number in `capex_usd_bn` only for sorting, e.g. "~220" → 220,
    "net ≤70 (gross up to ~95)" → 70; operators without capex go last; always display the original string).
- General mode: info is limited to `category`, `country` and aggregate counts. It returns no names,
  ids, tickers, investment counterparties or source URLs, and the rule is enforced server-side.
- UI: an info (ⓘ) button on the focus node opens a side panel with this data. On "Datacenter / AI",
  show the operator capex table ("Who is buying").

## Step 4 — Parallel edges and new data checks
- Some node pairs now have several supply edges (e.g. `nvidia -MAKES-> ct_ai_gpu` for GPUs *and*
  the Groq-based LPU; TSMC → Nvidia for wafers *and* CoWoS). Make sure the drill-down shows **one
  node per upstream company** with a list of its edges (item, category, status, confidence, source),
  not duplicate nodes.
- Grouping in General mode stays by `item_category`, so a supplier appears in each role it plays.

## Step 5 — Tests (must pass before done)
1. `/node/vertical_datacenter_ai/upstream` returns exactly **12** ChipType nodes (BMC added). Update
   the task-001 test that expected 11.
2. `/node/huawei/upstream?context=ct_ai_gpu` contains `smic` and `cxmt` (with `status: planned`)
   and does **not** contain `tsmc` or `samsung_memory`, whose edges are historical. With
   `include_history=true` they appear with `status: historical`.
3. `/node/nvidia/upstream?context=ct_ai_gpu` contains `kyec` and `samsung_foundry`, and still excludes
   `arm`, `lumentum` and `coherent`.
4. `/node/microsoft/upstream?context=ct_ai_asic` contains `intel` (planned) and `wiwynn`, and excludes
   `arm` (Cobalt CPU input).
5. `/node/ct_ai_gpu/upstream` returns Nvidia once (with two MAKES edges), plus AMD, Cerebras, Huawei
   and Cambricon.
6. `/node/vertical_datacenter_ai/info` lists 9 operators. `google` has `capex_usd_bn = "195-205"`,
   and the list is sorted with Amazon first.
7. `/node/nvidia/info` lists `investments_out` to `intel`, `synopsys`, `lumentum` and `coherent`.
8. `/node/oracle/map` contains `site_dc_stargate_abilene` and `lane_foxconn_gdl_stargate`.
9. `/node/nvidia/map?context=ct_ai_gpu` contains `lane_ap6_kyec`.
10. General-mode responses (upstream, map and info) contain no company or site names from **any**
    run's `nodes.csv`. Update the existing test, which only checked run 1.
11. No response from upstream or map ever includes an edge with `status: retracted`.

## Step 6 — Keep the docs current
Update `CLAUDE.md`:
- Seed command: `python data/seed/load_seed.py --rebuild`.
- Graph model: relationship `status` values and default visibility; context types `OPERATES_IN` and
  `INVESTS_IN`; relationships carry `seed_run` and `seed_runs`; `verified_in` marks re-checked edges.
- Rules:
  - Later runs update earlier edges only by repeating the exact key (from, to, type, item).
  - Something found to be wrong is marked `status: retracted` in a new run, never deleted by hand.
  - General mode must not leak identity through `/info` either.
- Current status: runs 1-3 loaded; task 003 done (once it is).

Update `docs/ROADMAP.md`:
- Phase 2: tick "Verify the 56 low confidence edges" as *partially* done ("25 of 56 upgraded in
  run 3; 31 remain"), tick the depth items run 3 covered, and add a new item "Run 4: remaining
  low-confidence edges + gaps listed in run3/README".
- Phase 4: note that `DisruptionEvent` nodes now include 10 resolved historical events
  (2011–2024), a first set of labels for the early-warning work.

## Done when
All tests pass. In the UI:
- Datacenter / AI → ⓘ shows the operator capex table.
- Datacenter / AI → AI GPU → Huawei shows SMIC and CXMT (planned), and TSMC appears greyed only
  with "Show history" on.
- TSMC in General mode shows the CoPoS tool makers as planned.
- ASML → upstream shows VDL ETG, Neways and Prodrive next to Zeiss, TRUMPF and Cymer.
