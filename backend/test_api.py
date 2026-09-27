"""API tests.

GeneralModeAllowlistTest runs without a database. GraphTest needs Neo4j running with run1 loaded
(`make seed`); otherwise it is skipped with a message saying so — it never falls back to fake data.
"""
import csv
import json
import re
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app
from db.neo4j_client import neo4j_client
from scripts.seed import RUN_DIR, get_driver, load_run_module, seed

SUPPLY_TYPES = ["COMPONENT_OF", "MAKES", "SUPPLIES", "FAB_OF", "INPUT_TO", "PRODUCES", "SOURCE_OF"]

with open(RUN_DIR / "nodes.csv", newline="", encoding="utf-8") as f:
    SEED_NODES = list(csv.DictReader(f))
COMPANY_NAMES = [n["name"] for n in SEED_NODES if n["label"] in ("Company", "Fab")]
COMPANY_IDS = [n["id"] for n in SEED_NODES if n["label"] in ("Company", "Fab")]


def leaked_terms(response_json, terms):
    """Terms that appear as whole words in the response (substring matching would flag 'Arm' in 'pharma')."""
    text = json.dumps(response_json, ensure_ascii=False).lower()
    return [t for t in terms if re.search(r"(?<!\w)" + re.escape(t.lower()) + r"(?!\w)", text)]


class GeneralModeAllowlistTest(unittest.TestCase):
    """The general-mode response is built from an allowlist, so extra fields from the query can't leak."""

    def test_extra_fields_from_query_are_dropped(self):
        leaky_focus = {"id": "nvidia", "label": "Company", "name": "Nvidia", "category": "Chip designer",
                       "event_count": 1}
        leaky_roles = [{"role": "HBM", "supplier_count": 3, "confidences": ["low", "high"],
                        "name": "SK hynix", "id": "sk_hynix", "source_url": "https://example.com"}]
        with patch.object(neo4j_client, "get_focus", AsyncMock(return_value=leaky_focus)), \
             patch.object(neo4j_client, "get_upstream_general", AsyncMock(return_value=leaky_roles)):
            body = TestClient(app).get("/node/nvidia/upstream?mode=general").json()

        self.assertEqual(body["focus"], {"label": "Company", "category": "Chip designer"})
        self.assertEqual(body["upstream"], [{"role": "HBM", "supplier_count": 3, "confidences": ["high", "low"]}])


class GraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = load_run_module()
        try:
            cls.driver = get_driver()
            with cls.driver.session() as s:
                seeded = s.run("MATCH (n {seed_run: $run}) RETURN count(n) AS c", run=run.SEED_RUN).single()["c"]
        except Exception as e:
            raise unittest.SkipTest(f"Neo4j not reachable ({type(e).__name__}) — start it and run `make seed`")
        if seeded != 144:
            cls.driver.close()
            raise unittest.SkipTest(f"run1 seed not loaded ({seeded} nodes) — run `make seed-reset`")
        # Entering the client keeps one event loop for all requests, which the async Neo4j driver needs.
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.driver.close()

    def upstream(self, node_id, **params):
        response = self.client.get(f"/node/{node_id}/upstream", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def upstream_ids(self, node_id, **params):
        return {up["id"] for up in self.upstream(node_id, **params)["upstream"]}

    # 1
    def test_context_filters_inputs_for_other_chip_types(self):
        ids = self.upstream_ids("nvidia", context="ct_ai_gpu")
        for unrelated in ("arm", "lumentum", "coherent"):
            self.assertNotIn(unrelated, ids)
        self.assertIn("tsmc", ids)
        self.assertIn("arm", self.upstream_ids("nvidia"))

    # 2
    def test_general_mode_contains_no_company_names_ids_or_urls(self):
        for node in SEED_NODES:
            for params in ({"mode": "general"}, {"mode": "general", "context": "ct_ai_gpu"}):
                body = self.upstream(node["id"], **params)
                self.assertEqual(leaked_terms(body, COMPANY_NAMES + COMPANY_IDS), [], node["id"])
                self.assertNotIn("http", json.dumps(body), node["id"])

    # 3
    def test_geo_edges_are_not_upstream(self):
        self.assertEqual(self.upstream("country_US")["upstream"], [])

    # 4
    def test_datacenter_vertical_has_exactly_the_11_chip_types(self):
        upstream = self.upstream("vertical_datacenter_ai")["upstream"]
        self.assertEqual(len(upstream), 11)
        self.assertTrue(all(up["label"] == "ChipType" for up in upstream))

    # 5
    def test_seed_loader_is_idempotent(self):
        def counts():
            with self.driver.session() as s:
                return (s.run("MATCH (n) RETURN count(n) AS c").single()["c"],
                        s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"])

        seed(self.driver)
        before = counts()
        seed(self.driver)
        self.assertEqual(counts(), before)

    # 6
    def test_every_returned_node_is_one_hop_away(self):
        for focus, ctx in [("vertical_datacenter_ai", None), ("ct_ai_gpu", "ct_ai_gpu"), ("nvidia", "ct_ai_gpu"),
                           ("nvidia", None), ("tsmc", None), ("asml", None), ("coherent", None)]:
            params = {"context": ctx} if ctx else {}
            ids = self.upstream_ids(focus, **params)
            self.assertTrue(ids, focus)
            with self.driver.session() as s:
                direct = s.run(
                    "MATCH ({id: $focus})<-[r]-(up) WHERE type(r) IN $types RETURN collect(up.id) AS ids",
                    focus=focus, types=SUPPLY_TYPES).single()["ids"]
            self.assertLessEqual(ids, set(direct), focus)

    def test_specific_mode_carries_provenance(self):
        tsmc = next(up for up in self.upstream("nvidia")["upstream"] if up["id"] == "tsmc")
        self.assertEqual(tsmc["label"], "Company")
        for edge in tsmc["edges"]:
            self.assertIn(edge["confidence"], ("high", "medium", "low"))
            self.assertTrue(edge["source_url"].startswith("http"))

    def test_unknown_node_is_404(self):
        self.assertEqual(self.client.get("/node/does_not_exist/upstream").status_code, 404)
        self.assertEqual(self.client.get("/node/does_not_exist/events").status_code, 404)

    def test_events_are_only_ongoing_or_upcoming(self):
        events = self.client.get("/node/tsmc/events").json()
        self.assertTrue(events)
        self.assertTrue(all(ev["status"] in ("ongoing", "upcoming") for ev in events))
        # ASML's only event is a proposed bill, which is not shown.
        self.assertEqual(self.client.get("/node/asml/events").json(), [])

    def test_verticals(self):
        verticals = self.client.get("/verticals").json()
        self.assertEqual(len(verticals), 7)
        self.assertEqual([v["id"] for v in verticals if v["populated"]], ["vertical_datacenter_ai"])


if __name__ == "__main__":
    unittest.main()
