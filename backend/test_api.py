"""API tests.

The *AllowlistTest classes run without a database. GraphTest needs Neo4j running with run1 + run2 loaded
(`make seed`); otherwise it is skipped with a message saying so — it never falls back to fake data.
"""
import json
import re
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import info_view
import map_view
from main import app
from db.neo4j_client import neo4j_client
from scripts.seed import get_driver, seed, seed_counts

SUPPLY_TYPES = ["COMPONENT_OF", "MAKES", "SUPPLIES", "INPUT_TO", "PRODUCES", "SOURCE_OF"]
SEED_TOTALS = (374, 979)  # runs 1-3 (`make seed`): seed nodes / relationships
RUN12_TOTALS = (262, 675)
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
        leaky_roles = [{"role": "HBM", "supplier_count": 3, "planned_count": 1, "historical_count": 0,
                        "confidences": ["low", "high"],
                        "name": "SK hynix", "id": "sk_hynix", "source_url": "https://example.com"}]
        with patch.object(neo4j_client, "get_focus", AsyncMock(return_value=leaky_focus)), \
             patch.object(neo4j_client, "get_upstream_general", AsyncMock(return_value=leaky_roles)):
            body = TestClient(app).get("/node/nvidia/upstream?mode=general").json()

        self.assertEqual(body["focus"], {"label": "Company", "category": "Chip designer"})
        self.assertEqual(body["upstream"], [{"role": "HBM", "supplier_count": 3, "planned_count": 1,
                                             "historical_count": 0, "confidences": ["high", "low"]}])


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
            raise unittest.SkipTest(f"seed not fully loaded ({counts}) — run `make seed`")
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

    # 003 test 10 (upstream and info; the map is covered by test_general_map_hides_identity...).
    # Names and ids come from the database, so they cover every run's nodes.csv.
    def test_general_mode_contains_no_company_names_ids_or_urls(self):
        for node_id in self.seed_node_ids:
            bodies = [self.upstream(node_id, mode="general", **params)
                      for params in ({}, {"context": "ct_ai_gpu"}, {"include_history": "true"})]
            bodies.append(self.get(f"/node/{node_id}/info", mode="general"))
            for body in bodies:
                self.assertEqual(leaked_terms(body, self.identity_names + self.all_ids), [], node_id)
                self.assertNotIn("http", json.dumps(body), node_id)

    def test_geo_edges_are_not_upstream(self):
        self.assertEqual(self.upstream("country_US")["upstream"], [])

    # 003 test 1 (BMC is the 12th)
    def test_datacenter_vertical_has_exactly_the_12_chip_types(self):
        upstream = self.upstream("vertical_datacenter_ai")["upstream"]
        self.assertEqual(len(upstream), 12)
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

    def test_every_country_has_a_centroid(self):
        with self.driver.session() as s:
            codes = set(s.run("MATCH (x:Site) RETURN collect(DISTINCT x.country) AS v").single()["v"])
            codes |= {c.replace("country_", "") for c in
                      s.run("MATCH (c:Country) RETURN collect(c.id) AS v").single()["v"]}
        self.assertEqual(sorted(codes - set(map_view.COUNTRY_CENTROIDS)), [])

    def test_map_rejects_other_focus_types(self):
        self.assertEqual(self.client.get("/node/country_US/map").status_code, 400)
        self.assertEqual(self.client.get("/node/vertical_datacenter_ai/map").status_code, 400)

    # 8 (and task 001's "loading twice changes nothing")
    # 002 test 8, 003 loader test (and task 001's "loading twice changes nothing").
    # Always ends with a full rebuild, so the other tests see the complete seed.
    def test_seed_loader_reset_and_reload(self):
        try:
            # Runs 1 + 2 only, as in task 002.
            self.assertEqual(seed(self.driver, runs=["run1", "run2"], rebuild=True), RUN12_TOTALS)
            self.assertEqual(seed(self.driver, runs=["run1", "run2"]), RUN12_TOTALS)
            self.assertEqual(seed(self.driver, reset=["run2"]), RUN1_TOTALS)
            with self.driver.session() as s:
                self.assertEqual(s.run("MATCH (c:Company {id: 'tsmc'}) RETURN c.name AS n").single()["n"], "TSMC")

            # All runs, then take run 3 back out.
            self.assertEqual(seed(self.driver, rebuild=True), SEED_TOTALS)
            self.assertEqual(seed(self.driver, reset=["run3"]), RUN12_TOTALS)
            with self.driver.session() as s:
                edge = s.run("MATCH (:Company {id: 'advantest'})-[r:SUPPLIES]->(:Company {id: 'nvidia'}) "
                             "RETURN r.seed_run AS run, r.seed_runs AS runs").single()
            # Run 3 updated this run-1 edge; resetting run 3 keeps the edge and its creator. Values run 3
            # wrote (confidence) stay until the next rebuild — documented loader behaviour.
            self.assertEqual(edge["run"], "run1-datacenter-gpu")
            self.assertEqual(edge["runs"], ["run1-datacenter-gpu"])
        finally:
            self.assertEqual(seed(self.driver, rebuild=True), SEED_TOTALS)


    # --- Run 3: status, parallel edges, info (task 003) ---

    def edges_by_node(self, node_id, **params):
        return {up["id"]: up["edges"] for up in self.upstream(node_id, **params)["upstream"]}

    # 2
    def test_planned_and_historical_suppliers(self):
        huawei = self.edges_by_node("huawei", context="ct_ai_gpu")
        self.assertIn("smic", huawei)
        self.assertEqual([e["status"] for e in huawei["cxmt"]], ["planned"])
        self.assertNotIn("tsmc", huawei)
        self.assertNotIn("samsung_memory", huawei)

        with_history = self.edges_by_node("huawei", context="ct_ai_gpu", include_history="true")
        for old in ("tsmc", "samsung_memory"):
            self.assertEqual({e["status"] for e in with_history[old]}, {"historical"})

    # 3
    def test_nvidia_gpu_suppliers_after_run3(self):
        ids = self.upstream_ids("nvidia", context="ct_ai_gpu")
        self.assertTrue({"kyec", "samsung_foundry"} <= ids)
        self.assertFalse({"arm", "lumentum", "coherent"} & ids)

    # 4
    def test_microsoft_asic_suppliers(self):
        microsoft = self.edges_by_node("microsoft", context="ct_ai_asic")
        self.assertIn("planned", {e["status"] for e in microsoft["intel"]})
        self.assertIn("wiwynn", microsoft)
        self.assertNotIn("arm", microsoft)

    # 5
    def test_parallel_edges_stay_on_one_node(self):
        upstream = self.upstream("ct_ai_gpu")["upstream"]
        ids = [up["id"] for up in upstream]
        self.assertEqual(ids.count("nvidia"), 1)
        nvidia = next(up for up in upstream if up["id"] == "nvidia")
        self.assertEqual([e["type"] for e in nvidia["edges"]], ["MAKES", "MAKES"])
        self.assertTrue({"amd", "cerebras", "huawei", "cambricon"} <= set(ids))

    # 6
    def test_datacenter_operators_sorted_by_capex(self):
        operators = self.get("/node/vertical_datacenter_ai/info")["operators"]
        self.assertEqual(len(operators), 9)
        self.assertEqual(operators[0]["id"], "amazon")
        google = next(o for o in operators if o["id"] == "google")
        self.assertEqual(google["capex_usd_bn"], "195-205")
        # Operators without a capex figure go last.
        seen_blank = False
        for o in operators:
            seen_blank = seen_blank or o["capex_usd_bn"] is None
            self.assertTrue(o["capex_usd_bn"] is None or not seen_blank, o["id"])

    # 7
    def test_nvidia_investments(self):
        out = {i["id"] for i in self.get("/node/nvidia/info")["investments_out"]}
        self.assertTrue({"intel", "synopsys", "lumentum", "coherent"} <= out)

    # 8
    def test_oracle_map_has_stargate(self):
        body = self.map("oracle")
        self.assertIn("site_dc_stargate_abilene", {s["id"] for s in body["sites"]})
        self.assertIn("lane_foxconn_gdl_stargate", {lane["id"] for lane in body["lanes"]})

    # 9
    def test_nvidia_map_has_kyec_test_lane(self):
        self.assertIn("lane_ap6_kyec", self.lane_ids("nvidia", context="ct_ai_gpu"))

    # 11
    def test_retracted_edges_are_never_returned(self):
        # No retracted edges exist in the seed yet, so add two temporary ones (not seed data, own marker):
        # an extra edge between an existing supplier pair, and the only edge of a new supplier pair.
        marker = "test-retracted"
        with self.driver.session() as s:
            s.run("MATCH (a:Company {id: 'tsmc'}), (b:Company {id: 'nvidia'}) "
                  "CREATE (a)-[:SUPPLIES {item: 'retracted test edge', status: 'retracted', confidence: 'high', "
                  "source_url: 'https://example.com', test_marker: $m}]->(b)", m=marker)
            s.run("MATCH (a:Company {id: 'arm'}), (b:Company {id: 'asml'}) "
                  "CREATE (a)-[:SUPPLIES {item: 'retracted test edge', status: 'retracted', confidence: 'high', "
                  "source_url: 'https://example.com', test_marker: $m}]->(b)", m=marker)
        try:
            for history in ("false", "true"):
                for node_id in ("nvidia", "asml"):
                    body = self.upstream(node_id, include_history=history)
                    statuses = {e["status"] for up in body["upstream"] for e in up["edges"]}
                    self.assertNotIn("retracted", statuses, node_id)
                    self.assertNotIn("arm", {up["id"] for up in body["upstream"]} if node_id == "asml" else set())
                companies = {c["id"] for c in self.map("asml", include_history=history)["companies"]}
                self.assertNotIn("arm", companies)
        finally:
            with self.driver.session() as s:
                s.run("MATCH ()-[r {test_marker: $m}]->() DELETE r", m=marker)
        self.assertEqual(seed_counts(self.driver), SEED_TOTALS)

    def test_planned_sites_are_flagged(self):
        sites = {s["id"]: s for s in self.map("kyec")["sites"]}
        self.assertTrue(sites["site_kyec_singapore"]["planned"])
        self.assertFalse(sites["site_kyec_miaoli"]["planned"] if "site_kyec_miaoli" in sites else False)

    def test_general_upstream_reports_planned_separately(self):
        roles = {r["role"]: r for r in self.upstream("tsmc", mode="general")["upstream"]}
        packaging = roles["Advanced packaging equipment"]
        self.assertEqual(packaging["supplier_count"], 0)
        self.assertEqual(packaging["planned_count"], 15)


class GeneralInfoAllowlistTest(unittest.TestCase):
    def test_general_info_keeps_only_category_country_and_counts(self):
        specific = {
            "id": "nvidia", "label": "Company", "name": "Nvidia", "category": "Chip designer", "country": "US",
            "ticker": "NVDA", "description": "Makes Blackwell GPUs", "site_count": 0,
            "events": [{"id": "ev_x", "name": "HBM shortage", "source_url": "https://example.com/ev"}],
            "capex": [],
            "investments_out": [{"id": "intel", "name": "Intel", "item": "equity", "amount_usd_bn": "5",
                                 "source_url": "https://example.com/inv"}],
            "investments_in": [],
        }
        general = info_view.to_general(specific)
        self.assertEqual(leaked_terms(general, ["nvidia", "NVDA", "Intel", "Blackwell", "ev_x", "HBM shortage"]), [])
        self.assertNotIn("http", json.dumps(general))
        self.assertEqual(general["investments_out_count"], 1)
        self.assertEqual(general["event_count"], 1)

    def test_capex_sort_key(self):
        self.assertEqual(info_view.capex_sort_key("~220"), (0, -220.0))
        self.assertEqual(info_view.capex_sort_key("net ≤70 (gross up to ~95)"), (0, -70.0))
        self.assertEqual(info_view.capex_sort_key("195-205"), (0, -195.0))
        self.assertEqual(info_view.capex_sort_key(None), (1, 0.0))


if __name__ == "__main__":
    unittest.main()
