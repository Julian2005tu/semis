"""API tests.

The *AllowlistTest classes run without a database. GraphTest needs Neo4j running with run1 + run2 loaded
(`make seed`); otherwise it is skipped with a message saying so — it never falls back to fake data.
"""
import json
import re
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import map_view
from main import app
from db.neo4j_client import neo4j_client
from scripts.seed import get_driver, seed, seed_counts

SUPPLY_TYPES = ["COMPONENT_OF", "MAKES", "SUPPLIES", "INPUT_TO", "PRODUCES", "SOURCE_OF"]
SEED_TOTALS = (262, 675)  # run1 + run2 seed nodes / relationships
RUN1_TOTALS = (144, 408)


def leaked_terms(response_json, terms):
    """Terms that appear as whole words in the response (substring matching would flag 'Arm' in 'pharma')."""
    text = json.dumps(response_json, ensure_ascii=False).lower()
    return [t for t in terms if re.search(r"(?<!\w)" + re.escape(t.lower()) + r"(?!\w)", text)]


def coordinates(value):
    """Every (lat, lon) pair anywhere in a JSON value."""
    if isinstance(value, dict):
        found = [(value["lat"], value["lon"])] if "lat" in value and "lon" in value else []
        return found + [c for v in value.values() for c in coordinates(v)]
    if isinstance(value, list):
        return [c for v in value for c in coordinates(v)]
    return []


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


class GeneralMapAllowlistTest(unittest.TestCase):
    def test_general_map_keeps_only_country_level_fields(self):
        specific = {
            "focus": {"id": "tsmc", "label": "Company", "name": "TSMC", "category": "Foundry"},
            "sites": [
                {"id": "fab_x", "name": "Secret Fab", "country": "TW", "role": "focus", "lat": 24.77, "lon": 121.01,
                 "source_url": "https://example.com/fab", "operators": [{"id": "tsmc", "name": "TSMC"}]},
                {"id": "site_y", "name": "Helium Plant", "country": "QA", "role": "lane endpoint",
                 "lat": 25.9, "lon": 51.5},
            ],
            "lanes": [{"id": "lane_z", "item": "helium", "mode": "sea", "from_site": "site_y", "to_site": "fab_x",
                       "source_url": "https://example.com/lane", "legs": [{"coords": [[51.5, 25.9]]}],
                       "chokepoints": [{"id": "cp_hormuz", "name": "Strait of Hormuz", "lat": 26.5, "lon": 56.3,
                                        "affected": True, "code": "HRM"}]}],
            "unmapped": [{"id": "nvidia", "name": "Nvidia"}],
        }
        general = map_view.to_general(specific)
        self.assertEqual(leaked_terms(general, ["tsmc", "Secret Fab", "Helium Plant", "fab_x", "site_y", "lane_z",
                                                "cp_hormuz", "nvidia", "helium"]), [])
        self.assertNotIn("http", json.dumps(general))
        self.assertEqual(general["lanes"], [{
            "from_country": "QA", "to_country": "TW", "mode": "sea", "count": 1,
            "chokepoints": [{"name": "Strait of Hormuz", "lat": 26.5, "lon": 56.3, "affected": True}]}])
        self.assertEqual(general["unmapped_count"], 1)


class GraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.driver = get_driver()
            counts = seed_counts(cls.driver)
        except Exception as e:
            raise unittest.SkipTest(f"Neo4j not reachable ({type(e).__name__}) — start it and run `make seed`")
        if counts != SEED_TOTALS:
            cls.driver.close()
            raise unittest.SkipTest(f"seed not fully loaded ({counts}) — run `make seed-reset`")
        with cls.driver.session() as s:
            # Everything that identifies a company or a place: names of companies/sites/lanes and all ids.
            cls.identity_names = s.run(
                "MATCH (n) WHERE (n:Company OR n:Site OR n:Lane) AND n.name IS NOT NULL "
                "RETURN collect(n.name) AS v").single()["v"]
            cls.all_ids = s.run("MATCH (n) WHERE n.id IS NOT NULL RETURN collect(n.id) AS v").single()["v"]
            cls.map_foci = s.run("MATCH (n) WHERE n:Company OR n:ChipType RETURN collect(n.id) AS v").single()["v"]
            cls.chokepoint_coords = {(r["lat"], r["lon"]) for r in s.run(
                "MATCH (h:Hub {hub_type: 'chokepoint'}) RETURN h.lat AS lat, h.lon AS lon")}
            cls.seed_node_ids = s.run(
                "MATCH (n) WHERE size(coalesce(n.seed_runs, [])) > 0 RETURN collect(n.id) AS v").single()["v"]
        # Entering the client keeps one event loop for all requests, which the async Neo4j driver needs.
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.driver.close()

    def get(self, url, **params):
        response = self.client.get(url, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def upstream(self, node_id, **params):
        return self.get(f"/node/{node_id}/upstream", **params)

    def upstream_ids(self, node_id, **params):
        return {up["id"] for up in self.upstream(node_id, **params)["upstream"]}

    def map(self, node_id, **params):
        return self.get(f"/node/{node_id}/map", **params)

    def lane_ids(self, node_id, **params):
        return {lane["id"] for lane in self.map(node_id, **params)["lanes"]}

    # --- Drill-down (task 001) ---

    def test_context_filters_inputs_for_other_chip_types(self):
        ids = self.upstream_ids("nvidia", context="ct_ai_gpu")
        for unrelated in ("arm", "lumentum", "coherent"):
            self.assertNotIn(unrelated, ids)
        self.assertIn("tsmc", ids)
        self.assertIn("arm", self.upstream_ids("nvidia"))

    def test_general_mode_contains_no_company_names_ids_or_urls(self):
        for node_id in self.seed_node_ids:
            for params in ({"mode": "general"}, {"mode": "general", "context": "ct_ai_gpu"}):
                body = self.upstream(node_id, **params)
                self.assertEqual(leaked_terms(body, self.identity_names + self.all_ids), [], node_id)
                self.assertNotIn("http", json.dumps(body), node_id)

    def test_geo_edges_are_not_upstream(self):
        self.assertEqual(self.upstream("country_US")["upstream"], [])

    def test_datacenter_vertical_has_exactly_the_11_chip_types(self):
        upstream = self.upstream("vertical_datacenter_ai")["upstream"]
        self.assertEqual(len(upstream), 11)
        self.assertTrue(all(up["label"] == "ChipType" for up in upstream))

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

    # 002 test 9
    def test_sites_are_not_upstream_and_companies_carry_site_count(self):
        upstream = self.upstream("nvidia", context="ct_ai_gpu")["upstream"]
        self.assertFalse([up["id"] for up in upstream if up["label"] in ("Site", "Fab")])
        tsmc = next(up for up in upstream if up["id"] == "tsmc")
        self.assertEqual(tsmc["site_count"], 10)
        # A fab's operator no longer has the fab as an input.
        self.assertFalse([up for up in self.upstream("tsmc")["upstream"] if up["label"] in ("Site", "Fab")])

    def test_unknown_node_is_404(self):
        for path in ("upstream", "events", "map"):
            self.assertEqual(self.client.get(f"/node/does_not_exist/{path}").status_code, 404)

    def test_events_are_only_ongoing_or_upcoming(self):
        events = self.get("/node/tsmc/events")
        self.assertTrue(events)
        self.assertTrue(all(ev["status"] in ("ongoing", "upcoming") for ev in events))
        # ASML's only event is a proposed bill, which is not shown.
        self.assertEqual(self.get("/node/asml/events"), [])

    def test_verticals(self):
        verticals = self.get("/verticals")
        self.assertEqual(len(verticals), 7)
        self.assertEqual([v["id"] for v in verticals if v["populated"]], ["vertical_datacenter_ai"])

    # --- Map mode (task 002) ---

    # 1
    def test_nvidia_map(self):
        body = self.map("nvidia", context="ct_ai_gpu")
        lanes = {lane["id"] for lane in body["lanes"]}
        for lane in ("lane_skh_hbm_ap6", "lane_samsung_hbm_ap6", "lane_tsmcaz_ap6", "lane_ibiden_ap6"):
            self.assertIn(lane, lanes)
        self.assertNotIn("lane_ap6_wistron", lanes)
        self.assertIn("nvidia", {c["id"] for c in body["unmapped"]})
        self.assertIn("lane_ap6_wistron", self.lane_ids("nvidia", context="ct_ai_gpu", include_customers="true"))

    # 2
    def test_tsmc_map_reaches_helium_via_distributor(self):
        lanes = self.lane_ids("tsmc", context="ct_ai_gpu")
        self.assertIn("lane_helium_qa_tsmc", lanes)
        self.assertIn("lane_asml_tsmc20", lanes)

    # 3
    def test_material_producer_lanes(self):
        lanes = self.lane_ids("shin_etsu")
        self.assertIn("lane_quartz_seh", lanes)
        self.assertIn("lane_poly_seh", lanes)

    # 4
    def test_asml_feeder_lanes(self):
        lanes = self.lane_ids("asml")
        for lane in ("lane_zeiss_ok_asml", "lane_zeiss_wz_asml", "lane_trumpf_asml", "lane_cymer_asml"):
            self.assertIn(lane, lanes)

    def all_specific_maps(self):
        for node_id in self.map_foci:
            for params in ({}, {"include_customers": "true"}, {"context": "ct_ai_gpu"}):
                yield node_id, self.map(node_id, **params)

    # 5 and 6
    def test_lane_endpoints_are_returned_and_hormuz_is_affected(self):
        hormuz_seen = False
        for node_id, body in self.all_specific_maps():
            site_ids = {s["id"] for s in body["sites"]}
            for lane in body["lanes"]:
                self.assertIn(lane["from_site"], site_ids, (node_id, lane["id"]))
                self.assertIn(lane["to_site"], site_ids, (node_id, lane["id"]))
                for cp in lane["chokepoints"]:
                    if cp["id"] == "cp_hormuz":
                        hormuz_seen = True
                        self.assertTrue(cp["affected"], (node_id, lane["id"]))
        self.assertTrue(hormuz_seen)

    # 7
    def test_general_map_hides_identity_and_exact_locations(self):
        centroids = {(lat, lon) for _, lat, lon in map_view.COUNTRY_CENTROIDS.values()}
        for node_id in self.map_foci:
            for params in ({}, {"include_customers": "true"}, {"context": "ct_ai_gpu"}):
                body = self.map(node_id, mode="general", **params)
                self.assertEqual(leaked_terms(body, self.identity_names + self.all_ids), [], node_id)
                self.assertNotIn("http", json.dumps(body), node_id)
                for coord in coordinates(body):
                    self.assertIn(coord, centroids | self.chokepoint_coords, node_id)

    def test_map_rejects_other_focus_types(self):
        self.assertEqual(self.client.get("/node/country_US/map").status_code, 400)
        self.assertEqual(self.client.get("/node/vertical_datacenter_ai/map").status_code, 400)

    # 8 (and task 001's "loading twice changes nothing")
    def test_seed_loader_reset_and_reload(self):
        self.assertEqual(seed(self.driver), SEED_TOTALS)
        self.assertEqual(seed(self.driver), SEED_TOTALS)
        try:
            self.assertEqual(seed(self.driver, runs=[], reset=["run2"]), RUN1_TOTALS)
            with self.driver.session() as s:
                self.assertEqual(s.run("MATCH (c:Company {id: 'tsmc'}) RETURN c.name AS n").single()["n"], "TSMC")
        finally:
            self.assertEqual(seed(self.driver, runs=["run2"]), SEED_TOTALS)


if __name__ == "__main__":
    unittest.main()
