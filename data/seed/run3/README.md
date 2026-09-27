# Run 3 — Depth pass across every stage of the Datacenter/AI chain

**Seed run tag:** `run3-depth-pass` · **As of:** September 2026 · load after run 1 and run 2
(`python data/seed/load_seed.py --rebuild` loads all runs in order).

Run 3 adds no new end market. It deepens every stage of the existing chain, from the datacenter
operators down to mined raw materials, and re-checks run 1's unverified edges.

**Totals after runs 1-3:** 374 nodes, 979 relationships.
**This run:** 112 new nodes, 304 new relationships, and 53 updates to run-1/run-2 edges.

## What's new, stage by stage

| Stage | Added |
|---|---|
| **Demand** | Capex for 7 operators as `OPERATES_IN` edges: Alphabet $195-205bn, Amazon ~$220bn, Microsoft ~$175bn, Meta $130-145bn, Oracle net ≤$70bn (FY27), CoreWeave $35-39bn, Nebius $20-25bn. New operators Oracle, CoreWeave, Nebius and xAI. Five flagship AI campuses as sites: Stargate Abilene, xAI Colossus 2, Project Rainier, Meta Prometheus, Microsoft Fairwater Atlanta |
| **Systems (ODM/OEM)** | Quanta, Wiwynn, Celestica, Dell and Supermicro, with customer edges (Wiwynn → Microsoft/Meta/AWS, Celestica → Google TPU racks, Dell → CoreWeave/xAI, Supermicro → xAI, Foxconn → Oracle for Stargate). Rack share for 2025: Foxconn 52%, Wistron 21%, Quanta 19% |
| **Chip design** | New chip type **BMC**: Aspeed has ~80% of it, so the datacenter now has 12 chip types. Power chips: TI, Navitas, AOS, Vicor and Renesas join Infineon and MPS. Nvidia's Groq-based LPU (made on Samsung 4nm). Cerebras. **China:** Huawei Ascend, Cambricon, Alibaba T-Head and Baidu Kunlunxin, supplied by SMIC and CXMT |
| **Foundry & memory** | SMIC; Intel Foundry 18A commitments from Microsoft and AWS (planned); TSMC for Cobalt 200; Samsung dual-sourcing HBM base dies with TSMC (planned); CXMT HBM3 (planned) |
| **Test** | KYEC (reportedly ~95% of Nvidia AI-chip testing); Teradyne; HBM4 wafer testers from Digital Frontier and UniTest; probe cards (FormFactor, Technoprobe, MJC) |
| **Advanced packaging** | 15 tool makers on TSMC's first CoPoS (panel-level CoWoS) supplier list, marked `planned`: Canon, SUSS, SCREEN, Kokusai, K&S, ASMPT, Disco, Towa, Scientech, GPTC, All Ring, plus AMAT, Lam, KLA and TEL |
| **Substrate materials** | Mitsubishi Gas Chemical, with the path Nittobo T-glass → MGC → substrate makers; T-glass shortage event |
| **Front-end equipment** | Segment leaders: TEL ~100% of EUV coater/developers, Lam leads etch, AMAT leads deposition, KLA >50% of key process-control steps. SCREEN, Ebara, Kokusai. China: NAURA, AMEC (5nm etch in TSMC validation), SMEE |
| **Equipment subsystems** | VAT (~75% of vacuum valves), Edwards, MKS, Advanced Energy. ASML module suppliers VDL ETG, Prodrive, Neways |
| **Mask chain** | AGC/Hoya shares; Mitsui Chemicals EUV pellicles; Lasertec (sole actinic EUV mask inspection); NuFlare and IMS mask writers |
| **Chemicals & materials** | Stella Chemifa and Soulbrain (HF), SK Specialty (NF3), Merck/EMD (precursors), Entegris and Fujimi (CMP), JX Advanced Metals, Plansee and Materion (sputtering targets) |
| **Raw materials** | Tungsten (China 83%), cobalt (DRC ore / China refining), tantalum (DRC, Rwanda), fluorspar (China 63%), rare earths (China 68%), indium (China 68%), tin; gallium and germanium shares updated (98% / 77%) |
| **Investments** | `INVESTS_IN` edges: Nvidia → Intel $5bn, → Synopsys $2bn, → Lumentum + Coherent $4bn; US government → Intel 9.9%; Micron → GlobalWafers $0.5bn; Teradyne → Technoprobe ~10% |
| **Sites & lanes** | 21 new sites (KYEC Miaoli/Singapore, VAT Haag/Penang, InnoLight Thailand, SMIC, CXMT, NAURA, AMEC, US rack plants, datacenters). 3 new lanes: TSMC AP6 → KYEC test, Foxconn Guadalajara → Stargate Abilene, Nittobo → Unimicron |
| **Disruption history** | 14 events, including resolved ones usable as training labels later: 2011 Tōhoku quake, 2019 Japan–Korea chemicals controls, 2021 Texas freeze, 2021 Renesas fire, 2022 Ukraine neon, 2023 China Ga/Ge licensing, 2024 Hualien quake, 2024 Helene/Spruce Pine, 2024 US HBM ban, 2025 China rare-earth controls, 2025-26 T-glass shortage, 2026 Section 232 chip tariff, 2026 DRAM shortage, 2026 proposed FCC optics ban |

## Verification of run 1

Run 1 had 56 low-confidence edges; **25 are now upgraded** (8 to high, 17 to medium) with sources.
Examples:
- Advantest's V93000 is the qualified tester at Nvidia and AMD, and Advantest holds 66% of SoC testers.
- Microsoft Cobalt 200 is built on 132 Arm Neoverse V3 cores on TSMC 3nm.
- AT&S supplies AMD from Kulim, Malaysia.
- GlobalWafers → Micron is a 10-year Texas deal.
- Intel Fab 52 runs 18A in high volume.

In addition, the 24 edges from TEL, Lam, AMAT and KLA to the six fabs now carry segment-share data.
China's gallium and germanium shares were updated to USGS figures.

The remaining 31 run-1 low edges are mostly per-customer EDA and wafer edges. They are plausible but still unverified.

Updates reuse the original edge key (from, to, type, item), so the loader overwrites those edges in
place. Their `seed_run` still names the run that created them; `seed_runs` lists every run that
wrote them; `verified_in` marks the run that re-checked them.

## New relationship property: `status`

| Value | Meaning | Count |
|---|---|---|
| absent / `active` | current supply relationship | — |
| `planned` | announced, qualifying or ramping (CoPoS tools, Intel 18A commitments, CXMT HBM, HBM4 testers, HBM base-die dual-sourcing) | 25 |
| `historical` | ended (Ukraine neon, TSMC's die bank for Huawei, Samsung HBM to Huawei before the Dec 2024 ban) | 3 |
| `retracted` | found to be wrong (none so far) | 0 |

## New context relationship types (never traversed by the drill-down)
- `(Company)-[:OPERATES_IN {capex_usd_bn, capex_period, capex_as_of}]->(EndMarketVertical)`
- `(Company|Country)-[:INVESTS_IN {amount_usd_bn, date}]->(Company)`

## Confidence of new supply edges
19 high, 70 medium, 53 low. Low edges are industry knowledge that this run did not verify:
per-customer chemical, gas and target edges, subsystem suppliers to equipment makers, probe-card
customers, Nittobo's plant location, and the Chinese equipment makers' sites.

## Known gaps
- Merchant photomask makers (Tekscend/Toppan, DNP, Photronics). Leading-edge masks are mostly
  made in-house by the fabs.
- Hua Hong, and China's packaging houses (JCET, Tongfu).
- Glass-core substrates.
- Datacenter power and cooling equipment (Vertiv, Schneider, Delta).
- Nvidia's Taiwan rack-assembly sites.
- Which Samsung fab makes the Groq LPU.
- Exact locations for most Chinese sites.

## Main sources
Test: [Wing VC on chip testing](https://www.wing.vc/content/the-chip-testing-bottleneck), [T.Media on KYEC](https://t.media/3177612), [BriefAsia on HBM4 testers](https://www.briefasia.com/en/article/south-korean-suppliers-hbm4-memory-testing-market) ·
Demand & systems: [TMT Finance capex](https://www.tmtfinance.com/intel/2026-hyperscaler-capex-tops-us700bn-analysis), [Supercycle capex roundup](https://supercyclehq.com/blog/reports/hyperscaler-capex-september-2026), [36Kr on rack ODM shares](https://eu.36kr.com/en/p/3590983777108229), [Maktinta on rack builders](https://www.maktinta.com/post/ai-server-rack-builders-and-hiring-2026), [Mexico Business News on Foxconn/Stargate](https://mexicobusiness.news/cloudanddata/news/foxconn-builds-nvidia-ai-servers-mexico-stargate-project), [NextBigFuture on AI campuses](https://www.nextbigfuture.com/2026/06/major-ai-data-center-build-projects-timelines-status-2026-2028.html) ·
Chips: [Taiwan News on Aspeed](https://www.taiwannews.com.tw/news/6411319), [Tom's Hardware on Groq 3](https://www.tomshardware.com/tech-industry/semiconductors/nvidias-20-billion-groq-deal-produces-its-first-chip), [The Substrate on China's AI chips](https://www.the-substrate.net/p/where-chinas-ai-chip-supply-chain), [The Register on Cerebras](https://www.theregister.com/ai-ml/2026/05/15/cerebras-wafer-scale-ai-bet-delivers-blockbuster-ipo/5240821), [Nutty on GPU VRMs](https://nuttycld.substack.com/p/the-ai-power-crisis-part-3), [Power Electronics News on 800 VDC](https://www.powerelectronicsnews.com/apec-2026-the-race-to-deliver-800-vdc-power-straight-to-the-gpu/) ·
Equipment & packaging: [Macrostream on the CoPoS supplier list](https://www.macrostream.ai/articles/6a38e3808bef2323d23d04af), [TrendForce on China equipment](https://www.trendforce.com/news/2026/01/12/news-chinas-domestic-chip-equipment-adoption-beats-2025-target-at-35-led-by-naura-amec/), [VAT Group](https://en.wikipedia.org/wiki/VAT_Group), [Tech Reader Daily on ASML](https://www.techreaderdaily.com/article/asml-lifts-guidance-to-45-billion-as-supply-chain-struggles) ·
Materials: [SemiconductorX on EUV mask blanks](https://semiconductorx.com/semiconductor-euv-mask-blanks.html), [Wafergraph materials](https://wafergraph.com/segment/materials/), [SemiconductorX on targets](https://semiconductorx.com/wafer-sputtering-targets.html), [Tom's Hardware on T-glass](https://www.tomshardware.com/tech-industry/artificial-intelligence/glass-cloth-could-be-the-next-great-ai-shortage-as-major-manufacturers-scramble-to-secure-critical-material-japanese-manufacturer-courted-by-apple-nvidia-google-and-amazon), [USGS on China's mineral production](https://pubs.usgs.gov/publication/ofr20261018/full), [Pillsbury on China's export controls](https://www.pillsburylaw.com/en/news-and-insights/china-suspends-export-controls-certain-critical-minerals-related-items.html) ·
Policy & events: [White House Section 232 proclamation](https://www.whitehouse.gov/presidential-actions/2026/01/adjusting-imports-of-semiconductors-semiconductor-manufacturing-equipment-and-their-derivative-products-into-the-united-states/), [Cignal AI on the FCC optics ban](https://cignal.ai/2026/08/fcc-ban-on-new-chinese-optical-modules/), [USITC on neon](https://www.usitc.gov/publications/332/executive_briefings/ebot_decarlo_goodman_ukraine_neon_and_semiconductors.pdf), [USITC on the 2019 Japan–Korea dispute](https://www.usitc.gov/publications/332/working_papers/the_south_korea-japan_trade_dispute_in_context_semiconductor_manufacturing_chemicals_and_concentrated_supply_chains.pdf).
Every row carries its own `source_url`.
