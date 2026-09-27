# Task 002 — Map mode: where things are made and how they travel

## Goal
Add a **Graph / Map** toggle to the drill-down navigator. When the focus is a company (or a chip type),
Map mode shows the production sites of the focus and of its current suppliers on a world map, plus
the shipment lanes between them — by air, sea or road, through which airports, ports and chokepoints.

Data: `data/seed/run2/` (read its README first). 60 sites with coordinates, 25 hubs/chokepoints,
40 lanes with precomputed geometry.

## Step 0 — Explore and plan
- Check how task 001 was implemented (upstream endpoint, context handling, frontend structure).
- Propose a plan and wait for approval.

## Step 1 — Switch to the multi-run loader
- The seed command now runs `python data/seed/load_seed.py run1 run2` (replaces
  `data/seed/run1/load_graph.py`; see `data/seed/README.md`).
- Run it against the local Neo4j and verify: seed nodes = **262**, seed relationships = **675**.
  Old `seed_run` tags on nodes are migrated to `seed_runs` lists automatically.

## Step 2 — Drill-down adjustments
- Remove `FAB_OF` from the traversed relationship types: sites never appear as upstream nodes
  (they now live on the map). `SITE_OF`, `FROM_SITE`, `TO_SITE`, `VIA` are context types too.
- Specific mode: add `site_count` for every upstream company (count of `SITE_OF`), shown as a small
  "N sites" chip on the node. Hide it in General mode.

## Step 3 — Backend: `GET /node/{node_id}/map?mode=specific|general&context=<ChipType id>&include_customers=false`

**Which companies are on the map (set S):**
- Focus is a Company: the focus + its upstream companies (same `context` filter as the drill-down)
  + companies that `PRODUCES` a RawMaterial that is upstream of the focus
  + if `include_customers`: companies the focus `SUPPLIES`.
- Focus is a ChipType: the companies that `MAKES` it.
- Other focus types: return 400 with a clear message (the UI disables the toggle).

**Sites:** every Site with `SITE_OF` → a company in S.

**Lanes:** a lane's commercial chain is `[from_company, *via_companies, to_company]`. Show the lane if
**at least two** chain members are in S. Always include a shown lane's `FROM_SITE` and `TO_SITE`
sites, even if their operator is not in S (flag them `role: "lane endpoint"`).

**Specific-mode response:**
- `companies`: id, name, category, role (`focus` / `supplier` / `material producer` / `customer`),
  `mapped` (has sites)
- `sites`: id, name, site_type, status, products, lat, lon, geo_precision, operators, confidence,
  source_url, active events (ongoing/upcoming `DisruptionEvent`s that `AFFECTS` the site)
- `lanes`: id, item, item_category, mode, mode_basis, typical_transit, distance_km, from/to site,
  from/to/via companies, `legs` (parsed from the `geometry` property), hubs in `VIA.seq` order,
  chokepoints with `affected` (true if an ongoing/upcoming event `AFFECTS` that Hub), confidence,
  source_url
- `unmapped`: companies in S without sites (e.g. Nvidia — fabless)

**General-mode response (enforced server-side, like the drill-down):** no company names, no site
names, no ids, no source URLs, no exact coordinates. Aggregate sites to `{country, role, count}`
placed at a country centroid (a small static centroid table in the backend is fine), and lanes to
`{from_country, to_country, mode, count, chokepoints}`.

Geometry is precomputed in the seed; no runtime routing. For future lanes without geometry: air =
great-circle, sea = the `searoute` Python package (install in a virtualenv with an up-to-date
setuptools — it fails to build with some older system setuptools).

## Step 4 — Frontend: Map mode
- **Toggle** "Graph / Map" in the navigator header, next to Specific/General. Switching keeps the
  focus, breadcrumb and `context`. Disabled with a tooltip for unsupported focus types.
- **Stack:** `maplibre-gl` via `react-map-gl` plus deck.gl layers. Use a free vector basemap that needs
  no API key (e.g. OpenFreeMap), a dark style that matches the app, and the required attribution.
  Check the tile provider's usage terms.
- **Sites:** circle markers coloured by company role (focus / supplier / material producer / customer /
  lane endpoint), sized a little larger for the focus. Label on hover; "N sites" clusters when zoomed
  out are welcome.
- **Lanes:** draw every leg from `legs`. Colour by mode (air / sea / road), dashed when the lane's
  confidence is `low` (same convention as the graph). Small markers for airports and ports along
  the lane.
- **Chokepoints:** warning markers; red and pulsing when `affected` is true.
- **Panels:** click a site → operator(s), type, status, products, geo precision ("approximate"),
  events, source link. Click a lane → item, mode, legs with hubs, transit estimate, `mode_basis`
  ("reported" vs "typical practice"), chokepoints, confidence, source link.
- **"Not on the map" list** in the side panel for `unmapped` companies, so gaps are visible
  (show "fabless — no production sites" for Nvidia/AMD-type designers).
- **Show customers** switch (off by default) → `include_customers=true`.
- Fit the view to the shown sites on load; legend for modes, confidence and chokepoints.
- General mode on the map: country bubbles with role counts and aggregated country-to-country lanes.

## Step 5 — Tests (must pass before done)
1. `/node/nvidia/map?context=ct_ai_gpu` contains lanes `lane_skh_hbm_ap6`, `lane_samsung_hbm_ap6`,
   `lane_tsmcaz_ap6`, `lane_ibiden_ap6`; does **not** contain `lane_ap6_wistron` unless
   `include_customers=true`; `unmapped` contains `nvidia`.
2. `/node/tsmc/map?context=ct_ai_gpu` contains `lane_helium_qa_tsmc` (reached via Air Liquide) and
   `lane_asml_tsmc20`.
3. `/node/shin_etsu/map` contains `lane_quartz_seh` and `lane_poly_seh` (material-producer rule).
4. `/node/asml/map` contains `lane_zeiss_ok_asml`, `lane_zeiss_wz_asml`, `lane_trumpf_asml`,
   `lane_cymer_asml`.
5. Every returned lane's from/to site is in the returned `sites`.
6. `cp_hormuz` is returned with `affected: true` wherever a lane passes it.
7. General-mode map responses contain no company or site names, no ids, no URLs, and only
   country-centroid coordinates.
8. Loader: after `load_seed.py run1 run2` → 262 seed nodes / 675 seed relationships;
   after `--reset run2` → 144 / 408 and TSMC still exists with its name; after reloading run2 →
   262 / 675 again.
9. Drill-down: `/node/nvidia/upstream?context=ct_ai_gpu` returns no Site/Fab nodes and TSMC has
   `site_count = 10`.

## Step 6 — Keep the docs current
Update `CLAUDE.md`:
- Stack: add MapLibre GL + deck.gl (map mode).
- Repo layout & commands: seed command is `python data/seed/load_seed.py run1 run2`.
- Graph model: add labels `Site`, `Hub`, `Lane`; add `SITE_OF`, `FROM_SITE`, `TO_SITE`, `VIA` to the
  context types; mark `FAB_OF` as legacy (not traversed); sites carry `lat`, `lon`, `location`.
- Rules: General mode must not leak identity on the map either (country-level only). Seed runs load
  through `data/seed/load_seed.py`; each run's `nodes.csv` lists every node its relationships touch.
- Current status: task 001 done, task 002 done (once it is), run 2 loaded.

Update `docs/ROADMAP.md`: tick the Phase 1 items that are done, add "Map mode (task 002)" to Phase 1,
and tick "Run 2: production sites and logistics lanes" in Phase 2.

## Done when
All tests pass, and in the UI I can go Datacenter / AI → AI GPU → Nvidia → **Map** and see TSMC's
Taiwan sites, SK hynix and Samsung in Korea, Ibiden in Gifu and the Arizona fab, with air lanes into
Taiwan; switching on "Show customers" adds the lanes to Fort Worth and Guadalajara; and clicking
through to ASML → Map shows Veldhoven with Oberkochen, Wetzlar, Ditzingen and San Diego feeding it.
