"""Assembles the /node/{id}/map response from the pieces neo4j_client fetches.

Specific mode: companies, sites, lanes and unmapped companies with names and sources.
General mode: built only from country-level aggregates (allowlisted keys), so no company or site
names, ids, source URLs or exact site coordinates can reach the client. Chokepoints keep their real
position: they are public geography and say nothing about who ships through them.
"""
import json
from collections import defaultdict

# When a company qualifies for several roles, the strongest one wins (and colours its sites).
ROLE_PRIORITY = ["focus", "supplier", "material producer", "customer"]

# Approximate country centroids for General mode (lat, lon). Covers every Country node in runs 1-2.
COUNTRY_CENTROIDS = {
    "AT": ("Austria", 47.6, 14.1),
    "BE": ("Belgium", 50.6, 4.7),
    "CN": ("China", 35.0, 103.0),
    "DE": ("Germany", 51.2, 10.4),
    "DZ": ("Algeria", 28.0, 2.6),
    "FR": ("France", 46.6, 2.4),
    "GB": ("United Kingdom", 54.0, -2.5),
    "IE": ("Ireland", 53.2, -8.0),
    "IN": ("India", 22.0, 79.0),
    "JP": ("Japan", 36.2, 138.3),
    "KR": ("South Korea", 36.4, 127.9),
    "MX": ("Mexico", 23.6, -102.5),
    "MY": ("Malaysia", 4.2, 102.0),
    "NL": ("Netherlands", 52.2, 5.5),
    "NO": ("Norway", 61.0, 9.0),
    "QA": ("Qatar", 25.3, 51.2),
    "RU": ("Russia", 61.5, 96.0),
    "SG": ("Singapore", 1.35, 103.82),
    "TW": ("Taiwan", 23.7, 121.0),
    "UA": ("Ukraine", 49.0, 31.4),
    "US": ("United States", 39.8, -98.6),
}


def company_set(focus, candidates):
    """Merges role candidates into S: {company_id: {id, name, category, role}}."""
    companies = {}
    if focus["label"] == "Company":
        companies[focus["id"]] = {"id": focus["id"], "name": focus["name"], "category": focus["category"],
                                  "role": "focus"}
    for role in ROLE_PRIORITY[1:]:  # stronger roles first, so the first role a company gets sticks
        for c in candidates.get(role, []):
            companies.setdefault(c["id"], {**c, "role": role})
    return companies


def _best_role(roles):
    return min(roles, key=ROLE_PRIORITY.index) if roles else "lane endpoint"


def build_specific(focus, companies, site_rows, lane_rows):
    sites = []
    mapped = set()
    for row in site_rows:
        s = row["site"]
        operator_ids = [o["id"] for o in row["operators"]]
        mapped.update(operator_ids)
        sites.append({
            **s,
            "operators": row["operators"],
            "role": _best_role([companies[o]["role"] for o in operator_ids if o in companies]),
            "events": row["events"],
        })

    lanes = []
    for row in lane_rows:
        lane = dict(row["lane"])
        names = {c["id"]: c for c in row["chain_companies"]}
        chain = [names.get(cid, {"id": cid, "name": cid}) for cid in row["chain"]]
        lane["legs"] = json.loads(lane.pop("geometry") or "[]")
        lane["from_site"], lane["to_site"] = row["from_site"], row["to_site"]
        lane["from_company"], lane["via_companies"], lane["to_company"] = chain[0], chain[1:-1], chain[-1]
        lane["hubs"] = [h for h in row["stops"] if h["kind"] != "chokepoint"]
        lane["chokepoints"] = [h for h in row["stops"] if h["kind"] == "chokepoint"]
        lanes.append(lane)

    company_list = [{**c, "mapped": c["id"] in mapped} for c in companies.values()]
    company_list.sort(key=lambda c: (ROLE_PRIORITY.index(c["role"]), c["name"]))
    return {
        "focus": focus,
        "companies": company_list,
        "sites": sites,
        "lanes": lanes,
        "unmapped": [c for c in company_list if not c["mapped"]],
    }


def to_general(specific):
    """Country-level view of a specific-mode map. Every key is written out here on purpose."""
    focus = specific["focus"]

    by_country = defaultdict(lambda: defaultdict(int))
    for s in specific["sites"]:
        by_country[s["country"]][s["role"]] += 1
    countries = []
    for code, roles in sorted(by_country.items()):
        name, lat, lon = COUNTRY_CENTROIDS[code]
        countries.append({
            "country": code, "name": name, "lat": lat, "lon": lon,
            "site_count": sum(roles.values()),
            "roles": [{"role": r, "count": n} for r, n in sorted(roles.items())],
        })

    site_country = {s["id"]: s["country"] for s in specific["sites"]}
    grouped = {}
    for lane in specific["lanes"]:
        key = (site_country[lane["from_site"]], site_country[lane["to_site"]], lane["mode"])
        g = grouped.setdefault(key, {"count": 0, "chokepoints": {}})
        g["count"] += 1
        for cp in lane["chokepoints"]:
            g["chokepoints"][cp["name"]] = {"name": cp["name"], "lat": cp["lat"], "lon": cp["lon"],
                                           "affected": cp["affected"]}
    lanes = [
        {"from_country": f, "to_country": t, "mode": mode, "count": g["count"],
         "chokepoints": sorted(g["chokepoints"].values(), key=lambda c: c["name"])}
        for (f, t, mode), g in sorted(grouped.items())
    ]

    return {
        "focus": {"label": focus["label"], "category": focus["category"]},
        "countries": countries,
        "lanes": lanes,
        "unmapped_count": len(specific["unmapped"]),
    }
