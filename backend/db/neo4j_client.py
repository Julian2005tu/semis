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
#   - only supply-flow edges; context edges (HEADQUARTERED_IN, LOCATED_IN, SUBSIDIARY_OF, AFFECTS)
#     never show up as upstream
#   - $ctx (a ChipType id or null) keeps only edges meant for that chip type, so Arm doesn't appear
#     as a GPU supplier of Nvidia

UPSTREAM_SPECIFIC_QUERY = """
MATCH (focus {id: $id})<-[r]-(up)
WHERE type(r) IN ['COMPONENT_OF','MAKES','SUPPLIES','FAB_OF','INPUT_TO','PRODUCES','SOURCE_OF']
  AND ($ctx IS NULL OR r.for_chiptypes IS NULL OR $ctx IN split(r.for_chiptypes, ';'))
WITH up, collect({
    type: type(r), item: r.item, item_category: r.item_category,
    share_estimate: r.share_estimate, confidence: r.confidence, source_url: r.source_url
}) AS edges
OPTIONAL MATCH (ev:DisruptionEvent)-[:AFFECTS]->(up)
WHERE ev.status IN ['ongoing', 'upcoming']
RETURN up.id AS id, labels(up)[0] AS label, up.name AS name, up.category AS category,
       edges, count(DISTINCT ev) AS event_count
ORDER BY name
"""

# General mode groups by the standardised input type of the edge (a company can play several roles),
# falling back to the upstream node's own category. Only role labels and counts leave the database.
UPSTREAM_GENERAL_QUERY = """
MATCH (focus {id: $id})<-[r]-(up)
WHERE type(r) IN ['COMPONENT_OF','MAKES','SUPPLIES','FAB_OF','INPUT_TO','PRODUCES','SOURCE_OF']
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


neo4j_client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
