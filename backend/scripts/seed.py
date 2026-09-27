"""Load a seed run into Neo4j with the credentials from backend/.env.

Usage (from the repo root):
    make seed          # upsert, safe to re-run
    make seed-reset    # remove this run's data (by seed_run), then load

Seed folders are append-only, so this imports each run's own load_graph.py instead of copying it.
"""
import argparse
import importlib.util
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

BACKEND_DIR = Path(__file__).resolve().parents[1]
RUN_DIR = BACKEND_DIR.parent / "data" / "seed" / "run1"


def load_run_module(run_dir=RUN_DIR):
    spec = importlib.util.spec_from_file_location(f"load_graph_{run_dir.name}", run_dir / "load_graph.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_driver():
    load_dotenv(BACKEND_DIR / ".env")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    return GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")))


def seed(driver, reset=False):
    """Loads the run and returns (nodes, relationships) tagged with its seed_run, counted in Neo4j."""
    run = load_run_module()
    nodes, rels = run.read_csv("nodes.csv"), run.read_csv("relationships.csv")
    with driver.session() as session:
        run.load(session, nodes, rels, reset=reset)
        n = session.run("MATCH (n {seed_run: $run}) RETURN count(n) AS c", run=run.SEED_RUN).single()["c"]
        r = session.run("MATCH ()-[r {seed_run: $run}]->() RETURN count(r) AS c", run=run.SEED_RUN).single()["c"]
    return run.SEED_RUN, n, r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete this seed's data before loading")
    args = ap.parse_args()

    with get_driver() as driver:
        seed_run, n, r = seed(driver, reset=args.reset)
    print(f"Neo4j now holds {n} nodes and {r} relationships with seed_run={seed_run}.")


if __name__ == "__main__":
    main()
