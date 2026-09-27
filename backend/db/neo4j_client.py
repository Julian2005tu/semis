import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables from .env file
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Cypher lives in named constants so every query the API can run is visible in one place.
# The supply-flow type list is written into each query (not built from input), and all user input
# goes in as parameters.
#
# Shared by both upstream queries:
#   - only supply-flow edges; context edges (HEADQUARTERED_IN, LOCATED_IN, SUBSIDIARY_OF, AFFECTS,
#     SITE_OF, FROM_SITE, TO_SITE, VIA) never show up as upstream. FAB_OF is legacy since run 2:
#     sites live on the map, not in the drill-down.
#   - $ctx (a ChipType id or null) keeps only edges meant for that chip type, so Arm doesn't appear
#     as a GPU supplier of Nvidia

UPSTREAM_SPECIFIC_QUERY = """
MATCH (focus {id: $id})<-[r]-(up)
WHERE type(r) IN ['COMPONENT_OF','MAKES','SUPPLIES','INPUT_TO','PRODUCES','SOURCE_OF']
  AND ($ctx IS NULL OR r.for_chiptypes IS NULL OR $ctx IN split(r.for_chiptypes, ';'))
WITH up, collect({
    type: type(r), item: r.item, item_category: r.item_category,
    share_estimate: r.share_estimate, confidence: r.confidence, source_url: r.source_url
}) AS edges
RETURN up.id AS id, labels(up)[0] AS label, up.name AS name, up.category AS category, edges,
       COUNT { MATCH (ev:DisruptionEvent)-[:AFFECTS]->(up) WHERE ev.status IN ['ongoing', 'upcoming'] }
           AS event_count,
       COUNT { MATCH (:Site)-[:SITE_OF]->(up) } AS site_count
ORDER BY name
"""

# General mode groups by the standardised input type of the edge (a company can play several roles),
# falling back to the upstream node's own category. Only role labels and counts leave the database.
UPSTREAM_GENERAL_QUERY = """
MATCH (focus {id: $id})<-[r]-(up)
WHERE type(r) IN ['COMPONENT_OF','MAKES','SUPPLIES','INPUT_TO','PRODUCES','SOURCE_OF']
  AND ($ctx IS NULL OR r.for_chiptypes IS NULL OR $ctx IN split(r.for_chiptypes, ';'))
WITH coalesce(r.item_category, up.category, labels(up)[0]) AS role, up, r
RETURN role, count(DISTINCT up) AS supplier_count, collect(DISTINCT r.confidence) AS confidences
ORDER BY role
"""

FOCUS_QUERY = """
MATCH (n {id: $id})
OPTIONAL MATCH (ev:DisruptionEvent)-[:AFFECTS]->(n)
WHERE ev.status IN ['ongoing', 'upcoming']
RETURN n.id AS id, labels(n)[0] AS label, n.name AS name, n.category AS category,
       count(DISTINCT ev) AS event_count
"""

EVENTS_QUERY = """
MATCH (ev:DisruptionEvent)-[:AFFECTS]->(n {id: $id})
WHERE ev.status IN ['ongoing', 'upcoming']
RETURN ev.id AS id, ev.name AS name, ev.date AS date, ev.status AS status,
       ev.severity AS severity, ev.description AS description, ev.source_url AS source_url
ORDER BY ev.date
"""

# --- Map mode ---------------------------------------------------------------------------------------
# The map shows a set of companies S (see map_view.py for how roles combine), their sites, and the
# lanes that connect them. Each query below fetches one piece; map_view.py assembles the response.

# Companies feeding the focus company directly (same edge types and context filter as the drill-down).
MAP_SUPPLIERS_QUERY = """
MATCH (:Company {id: $id})<-[r]-(c:Company)
WHERE type(r) IN ['COMPONENT_OF','MAKES','SUPPLIES','INPUT_TO','PRODUCES','SOURCE_OF']
  AND ($ctx IS NULL OR r.for_chiptypes IS NULL OR $ctx IN split(r.for_chiptypes, ';'))
RETURN DISTINCT c.id AS id, c.name AS name, c.category AS category
"""

# Miners/refiners of raw materials that feed the focus company (e.g. Sibelco → quartz → Shin-Etsu).
MAP_MATERIAL_PRODUCERS_QUERY = """
MATCH (:Company {id: $id})<-[r:INPUT_TO]-(:RawMaterial)<-[:PRODUCES]-(c:Company)
WHERE $ctx IS NULL OR r.for_chiptypes IS NULL OR $ctx IN split(r.for_chiptypes, ';')
RETURN DISTINCT c.id AS id, c.name AS name, c.category AS category
"""

# Companies the focus company supplies (only fetched when include_customers is on).
MAP_CUSTOMERS_QUERY = """
MATCH (:Company {id: $id})-[r:SUPPLIES]->(c:Company)
WHERE $ctx IS NULL OR r.for_chiptypes IS NULL OR $ctx IN split(r.for_chiptypes, ';')
RETURN DISTINCT c.id AS id, c.name AS name, c.category AS category
"""

MAP_CHIP_MAKERS_QUERY = """
MATCH (:ChipType {id: $id})<-[:MAKES]-(c:Company)
RETURN DISTINCT c.id AS id, c.name AS name, c.category AS category
"""

# A lane's commercial chain is [from_company, *via_companies, to_company]; it is shown when at least two
# chain positions are companies in S. Counting positions (not distinct companies) keeps intra-company
# lanes such as TSMC fab → TSMC packaging. Lanes tagged for other chip types are dropped, like edges.
MAP_LANES_QUERY = """
MATCH (l:Lane)
WHERE $ctx IS NULL OR l.for_chiptypes IS NULL OR $ctx IN split(l.for_chiptypes, ';')
WITH l, [l.from_company] + coalesce(split(l.via_companies, ';'), []) + [l.to_company] AS chain
WHERE size([c IN chain WHERE c IN $company_ids]) >= 2
MATCH (l)-[:FROM_SITE]->(fs:Site), (l)-[:TO_SITE]->(ts:Site)
RETURN l {.id, .item, .item_category, .mode, .mode_basis, .typical_transit, .distance_km, .geometry,
          .confidence, .source_url} AS lane,
       chain, fs.id AS from_site, ts.id AS to_site,
       COLLECT { MATCH (c:Company) WHERE c.id IN chain RETURN {id: c.id, name: c.name} } AS chain_companies,
       COLLECT {
           MATCH (l)-[v:VIA]->(h:Hub)
           WITH v, h ORDER BY v.seq
           RETURN {id: h.id, name: h.name, code: h.code, hub_type: h.hub_type, kind: v.kind,
                   leg_mode: v.leg_mode, lat: h.lat, lon: h.lon,
                   affected: EXISTS { MATCH (ev:DisruptionEvent)-[:AFFECTS]->(h)
                                      WHERE ev.status IN ['ongoing', 'upcoming'] }}
       } AS stops
ORDER BY l.id
"""

# Sites operated by a company in S, plus the lane endpoints we must always draw.
MAP_SITES_QUERY = """
MATCH (s:Site)
WHERE s.id IN $site_ids OR EXISTS { MATCH (s)-[:SITE_OF]->(c:Company) WHERE c.id IN $company_ids }
RETURN s {.id, .name, .site_type, .status, .products, .city, .country, .lat, .lon, .geo_precision,
          .confidence, .source_url} AS site,
       COLLECT { MATCH (s)-[:SITE_OF]->(c:Company) RETURN {id: c.id, name: c.name} } AS operators,
       COLLECT {
           MATCH (ev:DisruptionEvent)-[:AFFECTS]->(s) WHERE ev.status IN ['ongoing', 'upcoming']
           RETURN ev {.id, .name, .date, .status, .severity, .description, .source_url}
       } AS events
ORDER BY s.name
"""

VERTICALS_QUERY = """
MATCH (v:EndMarketVertical)
RETURN v.id AS id, v.name AS name, coalesce(v.populated, false) AS populated
ORDER BY v.populated DESC, v.name
"""


def _blank_to_none(edge):
    # The loader MERGEs on `item`, so edges without an item store "" rather than null.
    return {k: (None if v == "" else v) for k, v in edge.items()}


class Neo4jClient:
    def __init__(self, uri, user, password):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self.driver.close()

    async def _run(self, query, **params):
        async with self.driver.session() as session:
            result = await session.run(query, **params)
            return await result.data()

    async def get_focus(self, node_id: str):
        """Returns the node's id/label/name/category/event_count, or None if it doesn't exist."""
        rows = await self._run(FOCUS_QUERY, id=node_id)
        return rows[0] if rows else None

    async def get_upstream_specific(self, node_id: str, ctx):
        rows = await self._run(UPSTREAM_SPECIFIC_QUERY, id=node_id, ctx=ctx)
        for row in rows:
            row["edges"] = [_blank_to_none(e) for e in row["edges"]]
        return rows

    async def get_upstream_general(self, node_id: str, ctx):
        return await self._run(UPSTREAM_GENERAL_QUERY, id=node_id, ctx=ctx)

    async def get_events(self, node_id: str):
        return await self._run(EVENTS_QUERY, id=node_id)

    async def get_verticals(self):
        return await self._run(VERTICALS_QUERY)

    async def get_map_companies(self, node_id: str, label: str, ctx, include_customers: bool):
        """Candidate companies per role; map_view.company_set() merges them into set S."""
        if label == "ChipType":
            return {"supplier": await self._run(MAP_CHIP_MAKERS_QUERY, id=node_id)}
        return {
            "supplier": await self._run(MAP_SUPPLIERS_QUERY, id=node_id, ctx=ctx),
            "material producer": await self._run(MAP_MATERIAL_PRODUCERS_QUERY, id=node_id, ctx=ctx),
            "customer": await self._run(MAP_CUSTOMERS_QUERY, id=node_id, ctx=ctx) if include_customers else [],
        }

    async def get_map_lanes(self, company_ids, ctx):
        return await self._run(MAP_LANES_QUERY, company_ids=company_ids, ctx=ctx)

    async def get_map_sites(self, company_ids, site_ids):
        return await self._run(MAP_SITES_QUERY, company_ids=company_ids, site_ids=site_ids)


neo4j_client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
