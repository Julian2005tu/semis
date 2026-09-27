"""Load nodes.csv + relationships.csv into Neo4j (no APOC needed).

Usage:
    pip install neo4j
    export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=yourpassword
    python load_graph.py            # upsert (safe to re-run)
    python load_graph.py --reset    # first delete everything this seed created, then load

Every node and relationship gets `seed_run` so a seed can be removed or replaced cleanly
without touching data you added by hand.
"""
import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

SEED_RUN = "run1-datacenter-gpu"
HERE = Path(__file__).parent
BATCH = 500


def read_csv(name):
    with open(HERE / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def node_rows(nodes):
    by_label = defaultdict(list)
    for n in nodes:
        props = {k: v for k, v in n.items() if k not in ("id", "label", "props") and v != ""}
        if n.get("props"):
            props.update({k: v for k, v in json.loads(n["props"]).items() if v != ""})
        props["seed_run"] = SEED_RUN
        by_label[n["label"]].append({"id": n["id"], "props": props})
    return by_label


def rel_rows(rels, label_of):
    grouped = defaultdict(list)
    for r in rels:
        props = {k: v for k, v in r.items() if k not in ("from_id", "to_id", "type") and v != ""}
        props["seed_run"] = SEED_RUN
        key = (r["type"], label_of[r["from_id"]], label_of[r["to_id"]])
        grouped[key].append({"from": r["from_id"], "to": r["to_id"], "item": r["item"], "props": props})
    return grouped


def chunks(rows):
    for i in range(0, len(rows), BATCH):
        yield rows[i:i + BATCH]


def load(session, nodes, rels, reset=False):
    if reset:
        session.run("MATCH ()-[r {seed_run: $run}]-() DELETE r", run=SEED_RUN)
        session.run("MATCH (n {seed_run: $run}) DETACH DELETE n", run=SEED_RUN)

    by_label = node_rows(nodes)
    for label in by_label:
        session.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    for label, rows in by_label.items():
        for batch in chunks(rows):
            session.run(f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) SET n += row.props", rows=batch)

    label_of = {n["id"]: n["label"] for n in nodes}
    for (rtype, from_label, to_label), rows in rel_rows(rels, label_of).items():
        for batch in chunks(rows):
            # MERGE on (from, to, type, item): two SUPPLIES edges with different items stay separate.
            session.run(
                f"UNWIND $rows AS row "
                f"MATCH (a:{from_label} {{id: row.from}}), (b:{to_label} {{id: row.to}}) "
                f"MERGE (a)-[r:{rtype} {{item: row.item}}]->(b) SET r += row.props",
                rows=batch)
    return sum(len(v) for v in by_label.values()), len(rels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete this seed's data before loading")
    args = ap.parse_args()

    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    auth = (os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"])
    nodes, rels = read_csv("nodes.csv"), read_csv("relationships.csv")
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session() as session:
        n, r = load(session, nodes, rels, reset=args.reset)
    print(f"Loaded {n} nodes and {r} relationships (seed_run={SEED_RUN}).")


if __name__ == "__main__":
    main()
