"""Load one or more seed runs into Neo4j (no APOC needed).

Usage (from the repo root):
    pip install neo4j
    export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=...
    python data/seed/load_seed.py run1 run2              # load / upsert runs in order
    python data/seed/load_seed.py --reset run2 run2      # remove run2's data, then load it again
    python data/seed/load_seed.py --dry-run run1 run2    # validate files only, touch nothing

How runs share nodes:
- Every node carries `seed_runs` (list). A run that creates or references a node adds itself to it.
- Every relationship carries `seed_run` (string): exactly one run owns it.
- `--reset X` deletes X's relationships, removes X from every node's `seed_runs`, and deletes only
  nodes no run uses any more. Properties or extra labels X added to other runs' nodes stay.
- Each run's nodes.csv must list every node its relationships touch (rows for existing nodes may
  carry only id + label + new properties; empty cells never overwrite existing values).
Replaces data/seed/run1/load_graph.py, which tagged nodes with a single `seed_run`; that tag is
migrated to `seed_runs` automatically.
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
BASE_COLS = {"id", "label", "props", "extra_labels"}
REL_BASE = {"from_id", "to_id", "type", "props"}


def run_tag(folder):
    readme = SEED_DIR / folder / "SEED_RUN"
    return readme.read_text().strip() if readme.exists() else folder


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
    for r in rels:
        if not TYPE_RE.match(r["type"]):
            raise ValueError(f"{folder}: bad relationship type {r['type']!r}")
        for end in (r["from_id"], r["to_id"]):
            if end not in ids:
                raise ValueError(f"{folder}: relationship endpoint {end} missing from this run's nodes.csv")
    return ids


def node_props(n):
    props = {k: v for k, v in n.items() if k not in BASE_COLS and v not in ("", None)}
    if n.get("props"):
        props.update({k: v for k, v in json.loads(n["props"]).items() if v not in ("", None)})
    return props


def rel_props(r, tag):
    props = {k: v for k, v in r.items() if k not in REL_BASE and v not in ("", None)}
    if r.get("props"):
        props.update(json.loads(r["props"]))
    props["seed_run"] = tag
    return props


def chunks(rows):
    for i in range(0, len(rows), BATCH):
        yield rows[i:i + BATCH]


def migrate(session):
    session.run("MATCH (n) WHERE n.seed_run IS NOT NULL AND n.seed_runs IS NULL "
                "SET n.seed_runs = [n.seed_run] REMOVE n.seed_run")


def reset(session, tag):
    migrate(session)
    session.run("MATCH ()-[r]->() WHERE r.seed_run = $run DELETE r", run=tag)
    session.run("MATCH (n) WHERE $run IN n.seed_runs SET n.seed_runs = [x IN n.seed_runs WHERE x <> $run]", run=tag)
    session.run("MATCH (n) WHERE n.seed_runs = [] DETACH DELETE n")


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
            {"from": r["from_id"], "to": r["to_id"], "item": r.get("item", ""), "props": rel_props(r, tag)})
    for (rtype, fl, tl), rows in grouped.items():
        for batch in chunks(rows):
            # MERGE on (from, to, type, item): edges with different items stay separate.
            session.run(
                f"UNWIND $rows AS row MATCH (a:{fl} {{id: row.from}}), (b:{tl} {{id: row.to}}) "
                f"MERGE (a)-[r:{rtype} {{item: row.item}}]->(b) SET r += row.props",
                rows=batch)
    return tag, len(nodes), len(rels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="run folders under data/seed/, loaded in the given order")
    ap.add_argument("--reset", action="append", default=[], metavar="RUN",
                    help="remove this run's data before loading (repeatable)")
    ap.add_argument("--dry-run", action="store_true", help="validate files only")
    args = ap.parse_args()

    for folder in args.runs:
        n, r = read_run(folder)
        validate(folder, n, r)
    if args.dry_run:
        print("Files valid:", ", ".join(args.runs))
        return

    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session() as session:
        for folder in args.reset:
            reset(session, run_tag(folder))
            print(f"Reset {run_tag(folder)}")
        for folder in args.runs:
            tag, n, r = load_run(session, folder)
            print(f"Loaded {tag}: {n} node rows, {r} relationships")


if __name__ == "__main__":
    main()
