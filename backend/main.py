from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from db.neo4j_client import neo4j_client
import map_view
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Supply Chain API")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIDENCE_ORDER = ["high", "medium", "low"]


@app.on_event("shutdown")
async def shutdown_event():
    await neo4j_client.close()

@app.get("/")
def read_root():
    return {"message": "Supply Chain API running"}

@app.get("/verticals")
async def get_verticals():
    """All end markets for the 'Select End Market' dropdown; populated=false ones are 'coming soon'."""
    return await neo4j_client.get_verticals()

@app.get("/node/{node_id}/upstream")
async def get_node_upstream(
    node_id: str,
    mode: str = Query("specific", pattern="^(specific|general)$"),
    context: Optional[str] = Query(None, description="ChipType id; keeps only inputs meant for that chip type"),
):
    """
    Exactly one hop of supply-flow inputs into the focus node.

    specific: one entry per upstream node with every edge into the focus (item, share, confidence, source).
    general:  one entry per role with a supplier count. The response is built from an allowlist of keys,
              so no company name, id or source URL can reach the client — not even the focus node's.
    """
    focus = await neo4j_client.get_focus(node_id)
    if focus is None:
        raise HTTPException(status_code=404, detail="Node not found")

    if mode == "specific":
        return {
            "focus": focus,
            "upstream": await neo4j_client.get_upstream_specific(node_id, context),
        }

    roles = await neo4j_client.get_upstream_general(node_id, context)
    return {
        "focus": {"label": focus["label"], "category": focus["category"]},
        "upstream": [
            {
                "role": row["role"],
                "supplier_count": row["supplier_count"],
                "confidences": [c for c in CONFIDENCE_ORDER if c in row["confidences"]],
            }
            for row in roles
        ],
    }

@app.get("/node/{node_id}/map")
async def get_node_map(
    node_id: str,
    mode: str = Query("specific", pattern="^(specific|general)$"),
    context: Optional[str] = Query(None, description="ChipType id; same filter as the drill-down"),
    include_customers: bool = False,
):
    """
    Production sites of the focus (a Company or ChipType) and its current suppliers, plus the shipment
    lanes between them. General mode aggregates everything to countries (see map_view.to_general).
    """
    focus = await neo4j_client.get_focus(node_id)
    if focus is None:
        raise HTTPException(status_code=404, detail="Node not found")
    if focus["label"] not in ("Company", "ChipType"):
        raise HTTPException(status_code=400, detail="Map mode is available for companies and chip types only")

    candidates = await neo4j_client.get_map_companies(node_id, focus["label"], context, include_customers)
    companies = map_view.company_set(focus, candidates)
    lanes = await neo4j_client.get_map_lanes(list(companies), context)
    endpoint_sites = sorted({row["from_site"] for row in lanes} | {row["to_site"] for row in lanes})
    sites = await neo4j_client.get_map_sites(list(companies), endpoint_sites)

    specific = map_view.build_specific(focus, companies, sites, lanes)
    return specific if mode == "specific" else map_view.to_general(specific)

@app.get("/node/{node_id}/events")
async def get_node_events(node_id: str):
    """Ongoing or upcoming DisruptionEvents with an AFFECTS edge to the node."""
    if await neo4j_client.get_focus(node_id) is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return await neo4j_client.get_events(node_id)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
