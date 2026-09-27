# Seed data

Each `runN/` folder is one research run: `nodes.csv`, `relationships.csv`, a `README.md` describing
what it adds, and a `SEED_RUN` file with its tag. Runs are **append-only**. Corrections and new data
go into a new run folder, never into an existing one.

| Run | Tag | Adds |
|---|---|---|
| `run1/` | `run1-datacenter-gpu` | Datacenter/AI vertical; the GPU chain down to equipment, materials and countries; disruption events |
| `run2/` | `run2-sites-logistics` | 60 production sites with coordinates, 25 hubs/chokepoints, 40 shipment lanes (map mode) |
| `run3/` | `run3-depth-pass` | Depth pass across all stages: operators and capex, ODMs, BMC and power chips, China, test, CoPoS tools, subsystems, masks, chemicals, raw materials, investments, disruption history; 25 run-1 edges verified |

## Loading
```bash
python data/seed/load_seed.py --rebuild                  # recommended: wipe seed data, load run1..runN in order
python data/seed/load_seed.py run1 run2 run3             # upsert in order (safe to re-run)
python data/seed/load_seed.py --reset run3 run3          # replace run 3 only
python data/seed/load_seed.py --dry-run                  # validate every run folder without touching Neo4j
```
Needs `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in the environment.

## How runs combine
- Nodes carry a `seed_runs` list. Relationships carry `seed_run` (the run that created them) and
  `seed_runs` (every run that wrote them).
- A later run updates an earlier run's relationship by repeating its key (from, to, type, item).
  Non-empty values overwrite. Later runs win, so always load in ascending order; `--rebuild` does this.
- `--reset X` deletes only what no other run uses. Values X wrote onto other runs' data stay until the
  next `--rebuild`.
- Relationship `status`: absent/`active`, `planned`, `historical`, `retracted`. The loader keeps all
  of them; the API decides what to show.
