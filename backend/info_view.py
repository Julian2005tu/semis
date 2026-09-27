"""Assembles the /node/{id}/info response from the pieces neo4j_client.get_info() fetches.

Specific mode: the node's own fields, capex, investments and (for an end market) its operators.
General mode: built only from allowlisted keys — category, country and counts — so no names, ids,
tickers, investment counterparties or source URLs reach the client.
"""
import re

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def capex_sort_key(capex):
    """First number in the capex string, used only for sorting: "~220" → 220, "net ≤70 (…~95)" → 70.

    Operators without a figure sort last. The original string is always what gets displayed.
    """
    match = NUMBER_RE.search(capex or "")
    return (0, -float(match.group())) if match else (1, 0.0)


def build_specific(info):
    node = info["node"]
    result = {
        "id": node["id"],
        "label": node["label"],
        "name": node["name"],
        "category": node["category"],
        "country": node["country"],
        "ticker": node["ticker"],
        "description": node["description"],
        "site_count": node["site_count"],
        "events": node["events"],
        "capex": info["capex"],
        "investments_out": info["investments_out"],
        "investments_in": info["investments_in"],
    }
    if node["label"] == "EndMarketVertical":
        result["operators"] = sorted(info["operators"], key=lambda o: (capex_sort_key(o["capex_usd_bn"]), o["name"]))
    return result


def to_general(specific):
    """Category, country and counts only. Every key is written out here on purpose."""
    general = {
        "label": specific["label"],
        "category": specific["category"],
        "country": specific["country"],
        "site_count": specific["site_count"],
        "event_count": len(specific["events"]),
        "has_capex": bool(specific["capex"]),
        "investments_out_count": len(specific["investments_out"]),
        "investments_in_count": len(specific["investments_in"]),
    }
    if "operators" in specific:
        general["operator_count"] = len(specific["operators"])
    return general
