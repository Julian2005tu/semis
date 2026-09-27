# Seed data

Each `runN/` folder is one research run: `nodes.csv`, `relationships.csv`, a `README.md` describing
what it adds, and a `SEED_RUN` file with its tag. Runs are **append-only** — corrections and new data
go into a new run folder, never into an existing one.

| Run | Tag | Adds |
|---|---|---|
| `run1/` | `run1-datacenter-gpu` | Datacenter/AI vertical; GPU chain down to equipment, materials, countries; disruption events |
| `run2/` | `run2-sites-logistics` | 60 production sites with coordinates, 25 hubs/chokepoints, 40 shipment lanes (map mode) |

## Loading
```bash
python data/seed/load_seed.py run1 run2              # load in order (safe to re-run)
python data/seed/load_seed.py --reset run2 run2      # replace run 2 only
python data/seed/load_seed.py --dry-run run1 run2    # validate files without touching Neo4j
```
Needs `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in the environment.

`load_seed.py` replaces `run1/load_graph.py`. Nodes now carry a `seed_runs` list, so several runs can
share a node (e.g. TSMC). Resetting a run removes its relationships and deletes only nodes no other run
uses. Old single `seed_run` tags on nodes are migrated automatically on the first load.
