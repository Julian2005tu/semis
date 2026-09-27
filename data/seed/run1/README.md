# Semiconductor Supply-Chain Seed — Run 1: Datacenter/AI (GPU-deep)

**As of:** September 2026 · **144 nodes · 408 relationships** · every supply edge carries a source URL and a confidence level.

Run 1 maps the Datacenter/AI end market completely at the first layer (11 chip types that make up an AI datacenter and who makes them), then goes deep on the AI-accelerator chain: GPU / custom-ASIC designers → foundry, HBM, advanced packaging, substrates → front-end equipment and EUV subsystems → wafers, resists, gases → raw materials and source countries. The other six end-market verticals are defined as nodes (`populated=false`) so later runs slot in without schema changes.

## Files

| File | What it is |
|---|---|
| `nodes.csv` | One row per node: `id, label, name, category, country, ticker, description, source_url, props` (`props` = JSON of extra fields) |
| `relationships.csv` | One row per edge: `from_id, to_id, type, item, item_category, share_estimate, confidence, as_of, source_url, notes, for_chiptypes` |
| `load_graph.py` | Idempotent loader via the `neo4j` Python driver (no APOC). `--reset` removes only this seed's data (tagged `seed_run`) |
| `seed.cypher` | Same data as plain Cypher `MERGE` statements, for `cypher-shell -f seed.cypher` or the Neo4j Browser (multi-statement mode) |

**Load it:**
```bash
pip install neo4j
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=...
python load_graph.py --reset
```

## Schema

**Node labels:** `EndMarketVertical` (7), `ChipType` (11), `Company` (79), `Fab` (13 production/packaging sites), `RawMaterial` (8), `Country` (18), `DisruptionEvent` (8).

**Direction rule:** every supply-flow edge points the way goods flow — **upstream → downstream**. So "what feeds into X" is always `(X)<-[r]-(upstream)`, which is exactly the one-hop query your drill-down endpoint needs.

| Supply-flow types (traverse these) | Meaning |
|---|---|
| `COMPONENT_OF` | ChipType → EndMarketVertical |
| `MAKES` | Company → ChipType (with products + market share) |
| `SUPPLIES` | Company → Company (`item`, `item_category`, `share_estimate`) |
| `FAB_OF` | Fab → operating Company |
| `INPUT_TO` | RawMaterial → consuming Company |
| `PRODUCES` | Company → RawMaterial (miners/refiners) |
| `SOURCE_OF` | Country → RawMaterial |

| Context types (do **not** traverse in the drill-down) | Meaning |
|---|---|
| `HEADQUARTERED_IN`, `LOCATED_IN` | Company/Fab → Country (geopolitical layer) |
| `SUBSIDIARY_OF` | e.g. Solidigm → SK hynix, Cymer → ASML |
| `AFFECTS` | DisruptionEvent → any node (Phase 4 seed) |

**Three properties that matter for the UI:**
- `for_chiptypes` on `SUPPLIES` edges — which chip types an input is for. Nvidia's upstream mixes GPU, CPU, switch and optics inputs; when the user arrived via *Datacenter → AI GPU → Nvidia*, filter to edges whose `for_chiptypes` is empty or contains `ct_ai_gpu`. Without this, Arm (a Vera CPU input) would wrongly appear as a GPU supplier.
- `item_category` — standardised input type ("HBM", "Wafer fabrication", "Photoresist"…). **Group General mode by this, not by company category**: companies play several roles (TSMC is foundry *and* packager *and* HBM base-die maker; Shin-Etsu sells wafers *and* resist).
- `confidence` — `high` = official or multiple credible sources · `medium` = single credible report or analyst estimate · `low` = industry knowledge **not verified in this run** (56 edges; treat as a verification queue).

**Drill-down query (specific mode):**
```cypher
MATCH (focus {id: $id})<-[r]-(up)
WHERE type(r) IN ['COMPONENT_OF','MAKES','SUPPLIES','FAB_OF','INPUT_TO','PRODUCES','SOURCE_OF']
  AND ($ctx IS NULL OR r.for_chiptypes IS NULL OR $ctx IN split(r.for_chiptypes, ';'))
RETURN up.id AS id, labels(up)[0] AS label, up.name AS name, up.category AS category,
       type(r) AS rel, r.item AS item, r.item_category AS item_category,
       r.share_estimate AS share, r.confidence AS confidence, r.source_url AS source
```
**General mode:** same `MATCH`/`WHERE`, then
`RETURN CASE WHEN r.item_category IS NULL THEN up.category ELSE r.item_category END AS role, count(DISTINCT up) AS suppliers` — no names leave the server.

## What the research found (Sept 2026)

- **TSMC is the single point every AI accelerator passes through.** 72.5% of global foundry revenue in 2Q26; every hyperscaler ASIC and both merchant GPU vendors fabricate there. Rubin is on N3; MI450's compute die and EPYC Venice are on N2 (Fab 20 Hsinchu, Fab 22 Kaohsiung). Even Arizona-made wafers are still packaged in Taiwan.
- **CoWoS packaging is the tightest step.** Nvidia booked more than half of TSMC's 2026 CoWoS; TrendForce still sees a ~20% supply gap, and TSMC is pushing more work to Amkor and ASE/SPIL.
- **HBM is a three-supplier market with a clear leader.** SK hynix holds roughly 50–62% of HBM (methodologies disagree) and a reported 55–70% of Nvidia's Rubin HBM4; Samsung passed Nvidia qualification and is AMD's primary HBM4 supplier for MI455X; Micron is the third source. HBM4 is also where memory meets logic: SK hynix's base die is made by TSMC (N12), Samsung's by its own foundry (SF4), and Micron plans TSMC base dies from HBM4E.
- **Hidden chokepoints below the headline names:** Ajinomoto supplies ~95% of ABF build-up film (and raised prices ~30% in 2026); Carl Zeiss SMT is ASML's single optics supplier; Disco holds 70–80% of HBM wafer grinders; Namics is SK hynix's exclusive MR-MUF molding-compound supplier; Spruce Pine, NC supplies 70–90% of crucible-grade quartz; Lumentum is the only volume supplier of 200G/lane EML lasers for 1.6T optics.
- **Custom ASICs are a Broadcom-and-Marvell business.** Together ~95% of co-design; Broadcom holds Google TPU (through 2031), Meta MTIA and OpenAI; Marvell, Alchip and GUC cover AWS and Microsoft; MediaTek and Marvell are being added at Google.
- **Memory makers are in a supercycle.** 2Q26 DRAM revenue $154.7bn (+59.5% QoQ): Samsung 39.4%, SK hynix 24.9%, Micron 23.3%, CXMT 9.5%.

## Disruption watch list (seeded as `DisruptionEvent` nodes)

| Event | Status | Affects |
|---|---|---|
| Ras Laffan strikes / Strait of Hormuz closure → helium shortage (from 18 Mar 2026) | ongoing | Helium, Air Liquide, Korean fabs (≈⅔ Qatar-sourced), TSMC (3–6 months inventory) |
| Naphtha disruption hitting photoresist solvents/precursors | ongoing | TOK, JSR, Shin-Etsu, Fujifilm |
| ABF substrate shortage + ~30% Ajinomoto price hike | ongoing | Substrate makers → every AI accelerator |
| CoWoS capacity gap (~20%) | ongoing | TSMC, OSATs, Nvidia, Broadcom, AMD |
| HBM4 tightness (SK hynix expects worse in 2H26) | ongoing | HBM, Nvidia |
| China Ga/Ge/Sb export-ban suspension expires **27 Nov 2026** | upcoming | Gallium, germanium |
| Intel 18A yields may push Xeon 6+/Xeon 7 volume to 2027 | ongoing | Intel, Fab 52 |
| Proposed US bill targeting ASML DUV sales to China | proposed | ASML |

## Known limitations

- **Market-share figures conflict across sources** (especially HBM and CoWoS allocations). Where they do, `share_estimate` stores a range and `notes` says why; CoWoS numbers mix a Dec-2025 Morgan Stanley estimate with an Aug-2026 TrendForce figure.
- **Customer splits are rarely public.** Equipment, wafer and resist edges to specific fabs reflect a concentrated market (medium) rather than disclosed contracts.
- **One real cycle:** Nvidia supplies DSPs to Coherent and Coherent supplies laser capacity to Nvidia. The one-hop drill-down is unaffected, but any multi-hop traversal or shock propagation must carry a visited set.
- **Company-level edges mix product lines.** Multi-hop path analytics should respect `for_chiptypes`, or they will produce paths like "HBM → Nvidia → optical transceiver".
- Not yet covered: China's domestic AI chips (Huawei Ascend, Cambricon, SMIC), server/rack ODMs (Foxconn, Quanta, Wistron), datacenter operators' capex as the demand signal, and power semiconductors beyond a placeholder.

## Suggested next runs

1. **Vertical, same product:** deepen HBM (DRAM fab equipment, TSV, hybrid bonding) and EUV (Zeiss/Trumpf sub-suppliers, mask making, pellicles); verify the 56 low-confidence edges.
2. **Horizontal, same layer:** repeat the GPU-depth pass for server CPU, networking/optics and enterprise SSD.
3. **Second vertical:** Automotive (MCUs, power, analog) — it reuses Infineon, TSMC, GlobalFoundries and wafer suppliers, which makes the shared-capacity overlap query meaningful.
4. **Demand side:** hyperscaler capex and datacenter operator nodes, then link `RawMaterial.price_series` to TimescaleDB for the Phase 3/4 price work.
