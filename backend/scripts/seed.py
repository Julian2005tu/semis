"""Load seed runs into Neo4j with the credentials from backend/.env.

Usage (from the repo root):
    make seed          # load/upsert run1 then run2, safe to re-run
    make seed-reset    # remove both runs' data (by seed tag), then load them again

Thin wrapper around data/seed/load_seed.py (the multi-run loader), which reads its credentials from the
environment. Seed folders are append-only, so we import the loader instead of copying it.
"""
import argparse
import importlib.util
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_DIR = BACKEND_DIR.parent / "data" / "seed"
RUNS = ["run1", "run2"]


def load_seed_module():
    spec = importlib.util.spec_from_file_location("load_seed", SEED_DIR / "load_seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_driver():
    load_dotenv(BACKEND_DIR / ".env")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    return GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")))


def seed_counts(driver):
    """(nodes, relationships) that belong to any seed run."""
    with driver.session() as s:
        n = s.run("MATCH (n) WHERE size(coalesce(n.seed_runs, [])) > 0 RETURN count(n) AS c").single()["c"]
        r = s.run("MATCH ()-[r]->() WHERE r.seed_run IS NOT NULL RETURN count(r) AS c").single()["c"]
    return n, r


def seed(driver, runs=RUNS, reset=()):
    """Resets the runs in `reset`, loads `runs` in order, and returns seed_counts()."""
    loader = load_seed_module()
    with driver.session() as session:
        for folder in reset:
            loader.reset(session, loader.run_tag(folder))
        for folder in runs:
            loader.load_run(session, folder)
    return seed_counts(driver)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", default=RUNS, help="run folders under data/seed/, in load order")
    ap.add_argument("--reset", action="append", default=[], metavar="RUN",
                    help="remove this run's data before loading (repeatable)")
    args = ap.parse_args()

    with get_driver() as driver:
        n, r = seed(driver, args.runs, args.reset)
    print(f"Loaded {', '.join(args.runs)}. Neo4j now holds {n} seed nodes and {r} seed relationships.")


if __name__ == "__main__":
    main()
