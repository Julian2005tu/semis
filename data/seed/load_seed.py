"""Load seed runs into Neo4j (no APOC needed).

Usage (from the repo root):
    pip install neo4j
    export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=...
    python data/seed/load_seed.py run1 run2 run3           # load / upsert runs in order (safe to re-run)
    python data/seed/load_seed.py --rebuild                # delete ALL seed data, reload every runN folder in order
    python data/seed/load_seed.py --reset run3 run3        # remove run3's data, then load it again
    python data/seed/load_seed.py --dry-run run1 run2 run3 # validate files only, touch nothing

How runs share data:
- Nodes carry `seed_runs` (list): every run that creates, references or updates the node.
- Relationships carry `seed_run` (the run that created them) and `seed_runs` (every run that wrote
  them). A later run can update an earlier run's relationship by repeating its key
  (from, to, type, item): its non-empty values overwrite, and it is added to `seed_runs`.
- Later runs win: always load runs in ascending order. `--rebuild` does exactly that from scratch
  and is the recommended way to get a clean, deterministic state.
- `--reset X` removes X from every node's and relationship's `seed_runs` and deletes whatever no run
  uses any more. Property values X wrote onto other runs' data stay until the next `--rebuild`.
- Each run's nodes.csv lists every node its relationships touch (rows for existing nodes may carry
  only id + label + new properties; empty cells never overwrite existing values).
- Relationship `status`: absent/"active" = current, "planned" = announced/ramping, "historical" =
  ended, "retracted" = found to be wrong. Queries decide what to show; the loader never deletes them.
Replaces data/seed/run1/load_graph.py. Older single `seed_run` tags are migrated automatically.
"""
import argparse
import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

SEED_DIR = Path(__file__).parent
BATCH = 500
LABEL_RE = re.compile(r"^[A-Z][A-Za-z]*$")
TYPE_RE = re.compile(r"^[A-Z][A-Z_]*$")
RUN_RE = re.compile(r"^run(\d+)$")
BASE_COLS = {"id", "label", "props", "extra_labels"}
REL_BASE = {"from_id", "to_id", "type", "props"}
STATUSES = {"", "active", "planned", "historical", "retracted"}


def run_tag(folder):
    f = SEED_DIR / folder / "SEED_RUN"
    return f.read_text().strip() if f.exists() else folder


def all_runs():
    runs = [p.name for p in SEED_DIR.iterdir() if p.is_dir() and RUN_RE.match(p.name)]
    return sorted(runs, key=lambda r: int(RUN_RE.match(r).group(1)))


def read_run(folder):
    d = SEED_DIR / folder
    with open(d / "nodes.csv", newline="", encoding="utf-8") as f:
        nodes = list(csv.DictReader(f))
    with open(d / "relationships.csv", newline="", encoding="utf-8") as f:
        rels = list(csv.DictReader(f))
    return nodes, rels


def validate(folder, nodes, rels):
    ids = {}
    for n in nodes:
        if not LABEL_RE.match(n["label"]):
            raise ValueError(f"{folder}: bad label {n['label']!r}")
        for extra in filter(None, (n.get("extra_labels") or "").split(";")):
            if not LABEL_RE.match(extra):
                raise ValueError(f"{folder}: bad extra label {extra!r}")
        if n["id"] in ids:
            raise ValueError(f"{folder}: duplicate node {n['id']}")
        ids[n["id"]] = n["label"]
    seen = set()
    for r in rels:
        if not TYPE_RE.match(r["type"]):
            raise ValueError(f"{folder}: bad relationship type {r['type']!r}")
        for end in (r["from_id"], r["to_id"]):
            if end not in ids:
                raise ValueError(f"{folder}: relationship endpoint {end} missing from this run's nodes.csv")
        if (r.get("status") or "") not in STATUSES:
            raise ValueError(f"{folder}: bad status {r['status']!r}")
        key = (r["from_id"], r["to_id"], r["type"], r.get("item", ""))
        if key in seen:
            raise ValueError(f"{folder}: duplicate relationship {key}")
        seen.add(key)
    return ids


def node_props(n):
    props = {k: v for k, v in n.items() if k not in BASE_COLS and v not in ("", None)}
    if n.get("props"):
        props.update({k: v for k, v in json.loads(n["props"]).items() if v not in ("", None)})
    return props


def rel_props(r):
    props = {k: v for k, v in r.items() if k not in REL_BASE and v not in ("", None)}
    if r.get("props"):
        props.update({k: v for k, v in json.loads(r["props"]).items() if v not in ("", None)})
    props.pop("seed_run", None)
    return props


def chunks(rows):
    for i in range(0, len(rows), BATCH):
        yield rows[i:i + BATCH]


def migrate(session):
    session.run("MATCH (n) WHERE n.seed_run IS NOT NULL AND n.seed_runs IS NULL "
                "SET n.seed_runs = [n.seed_run] REMOVE n.seed_run")
    session.run("MATCH ()-[r]->() WHERE r.seed_run IS NOT NULL AND r.seed_runs IS NULL "
                "SET r.seed_runs = [r.seed_run]")


def reset(session, tag):
    migrate(session)
    session.run("MATCH ()-[r]->() WHERE $run IN r.seed_runs "
                "SET r.seed_runs = [x IN r.seed_runs WHERE x <> $run]", run=tag)
    session.run("MATCH ()-[r]->() WHERE r.seed_runs = [] DELETE r")
    session.run("MATCH (n) WHERE $run IN n.seed_runs SET n.seed_runs = [x IN n.seed_runs WHERE x <> $run]", run=tag)
    session.run("MATCH (n) WHERE n.seed_runs = [] DETACH DELETE n")


def rebuild(session):
    session.run("MATCH (n) WHERE n.seed_runs IS NOT NULL OR n.seed_run IS NOT NULL DETACH DELETE n")


def load_run(session, folder):
    tag = run_tag(folder)
    nodes, rels = read_run(folder)
    label_of = validate(folder, nodes, rels)
    migrate(session)

    by_label, extra = defaultdict(list), defaultdict(list)
    for n in nodes:
        p = node_props(n)
        by_label[n["label"]].append({"id": n["id"], "props": p, "lat": p.get("lat"), "lon": p.get("lon")})
        for e in filter(None, (n.get("extra_labels") or "").split(";")):
            extra[(n["label"], e)].append(n["id"])
    for label in list(by_label) + [e for _, e in extra]:
        session.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    for label, rows in by_label.items():
        for batch in chunks(rows):
            session.run(
                f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) SET n += row.props "
                "SET n.seed_runs = CASE WHEN $run IN coalesce(n.seed_runs, []) THEN n.seed_runs "
                "ELSE coalesce(n.seed_runs, []) + $run END "
                "FOREACH (_ IN CASE WHEN row.lat IS NULL THEN [] ELSE [1] END | "
                "SET n.location = point({latitude: toFloat(row.lat), longitude: toFloat(row.lon)}))",
                rows=batch, run=tag)
    for (label, e), id_list in extra.items():
        session.run(f"UNWIND $ids AS id MATCH (n:{label} {{id: id}}) SET n:{e}", ids=id_list)

    grouped = defaultdict(list)
    for r in rels:
        grouped[(r["type"], label_of[r["from_id"]], label_of[r["to_id"]])].append(
            {"from": r["from_id"], "to": r["to_id"], "item": r.get("item", ""), "props": rel_props(r)})
    for (rtype, fl, tl), rows in grouped.items():
        for batch in chunks(rows):
            # MERGE key (from, to, type, item): edges with different items stay separate;
            # repeating an earlier run's key updates that edge.
            session.run(
                f"UNWIND $rows AS row MATCH (a:{fl} {{id: row.from}}), (b:{tl} {{id: row.to}}) "
                f"MERGE (a)-[r:{rtype} {{item: row.item}}]->(b) "
                "ON CREATE SET r.seed_run = $run "
                "SET r += row.props "
                "SET r.seed_runs = CASE WHEN $run IN coalesce(r.seed_runs, []) THEN r.seed_runs "
                "ELSE coalesce(r.seed_runs, []) + $run END",
                rows=batch, run=tag)
    return tag, len(nodes), len(rels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", help="run folders under data/seed/, loaded in the given order")
    ap.add_argument("--rebuild", action="store_true",
                    help="delete all seed data, then load the given runs (default: every runN folder, ascending)")
    ap.add_argument("--reset", action="append", default=[], metavar="RUN",
                    help="remove this run's data before loading (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="validate files only")
    args = ap.parse_args()

    runs = args.runs or (all_runs() if (args.rebuild or args.dry_run) else [])
    if not runs and not args.reset:
        ap.error("name the runs to load, or use --rebuild")
    for folder in runs:
        n, r = read_run(folder)
        validate(folder, n, r)
    if args.dry_run:
        print("Files valid:", ", ".join(runs))
        return

    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session() as session:
        if args.rebuild:
            rebuild(session)
            print("Deleted all seed data")
        for folder in args.reset:
            reset(session, run_tag(folder))
            print(f"Reset {run_tag(folder)}")
        for folder in runs:
            tag, n, r = load_run(session, folder)
            print(f"Loaded {tag}: {n} node rows, {r} relationships")


if __name__ == "__main__":
    main()
