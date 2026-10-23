"""Reference implementation of bounded, date-aware graph traversal."""
from datetime import date
from .graph_export import graph_records


def active(record, on):
    return record["valid_from"] <= on < record["valid_to"]


def resolve_entity(data, value):
    records = data["entities"] + data["disruptions"]
    exact = [r for r in records if value.casefold() in (r["id"].casefold(), r["name"].casefold())]
    return exact or [r for r in records if value.casefold() in r["name"].casefold()]


def validate(data):
    errors, warnings = [], []
    records = sum((data[k] for k in ("entities", "sourcing", "routes", "disruptions", "evidence")), [])
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate record IDs")
    entities = {e["id"]: e for e in data["entities"]}
    evidence = {e["id"] for e in data["evidence"]}

    def ref(value, label, context):
        if value not in entities or entities[value]["label"] != label:
            errors.append(f"{context}: invalid {label} reference {value}")

    for entity in entities.values():
        id, label = entity["id"], entity["label"]
        if label == "ProductionFacility":
            ref(entity["supplier"], "Supplier", id)
            for component in entity["components"]:
                ref(component, "Component", id)
        if label == "SKU":
            ref(entity["category"], "Category", id)
            for field, target in [("components", "Component"), ("vendors", "Vendor"), ("dcs", "DC")]:
                for value in entity[field]:
                    ref(value, target, id)
        if label == "Store":
            ref(entity["primary_dc"], "DC", id)
            ref(entity["backup_dc"], "DC", id)
    if data["master_evidence"] not in evidence:
        errors.append("Missing master evidence")
    for record in data["sourcing"] + data["routes"] + data["disruptions"]:
        id = record["id"]
        try:
            if date.fromisoformat(record["valid_from"]) >= date.fromisoformat(record["valid_to"]):
                errors.append(f"{id}: invalid validity interval")
        except (ValueError, KeyError):
            errors.append(f"{id}: missing or invalid dates")
        if record.get("evidence") is None:
            warnings.append(f"{id}: missing source evidence; cannot support a confirmed dependency")
        elif record["evidence"] not in evidence:
            errors.append(f"{id}: dangling evidence reference")
    for record in data["sourcing"] + data["routes"]:
        id = record["id"]
        if record["role"] not in {"active", "backup"} or record["approval"] not in {"approved", "pending", "rejected"}:
            errors.append(f"{id}: invalid role or approval")
        ref(record["sku"], "SKU", id)
        ref(record["vendor"], "Vendor", id)
        sku = entities.get(record["sku"], {})
        if record["vendor"] not in sku.get("vendors", []):
            errors.append(f"{id}: vendor not approved for SKU")
        if "facility" in record:
            ref(record["component"], "Component", id)
            ref(record["facility"], "ProductionFacility", id)
            if record["component"] not in sku.get("components", []):
                errors.append(f"{id}: component not required by SKU")
            if record["component"] not in entities.get(record["facility"], {}).get("components", []):
                errors.append(f"{id}: facility cannot produce component")
        else:
            ref(record["dc"], "DC", id)
            ref(record["store"], "Store", id)
            if record["dc"] not in sku.get("dcs", []):
                errors.append(f"{id}: DC outside SKU distribution scope")
    for record in data["disruptions"]:
        target = entities.get(record["target"])
        if not target or target["label"] not in {"Supplier", "ProductionFacility", "Component", "DC"}:
            errors.append(f"{record['id']}: invalid disruption target")
    return {"errors": errors, "warnings": warnings}


def investigate(data, target, on=None):
    on = on or data["default_date"]
    on = date.fromisoformat(on).isoformat()
    matches = resolve_entity(data, target)
    if len(matches) != 1:
        return {"status": "clarification_required" if matches else "not_found",
                "query": target, "candidates": [{"id": r["id"], "name": r["name"]} for r in matches]}
    selected = matches[0]
    entities = {e["id"]: e for e in data["entities"]}
    source_ids = {e["id"] for e in data["evidence"]}
    _, graph_edges = graph_records(data)
    disruption = selected if selected["label"] == "Disruption" else None
    if disruption and not active(disruption, on):
        return {"status": "outside_disruption_window", "date": on, "target": selected["id"]}
    root = entities[disruption["target"]] if disruption else selected
    if root["label"] not in {"Supplier", "ProductionFacility", "Component", "DC"}:
        return {"status": "unsupported_target", "target": root["id"]}

    def affected(s):
        return ((root["label"] == "Supplier" and entities[s["facility"]]["supplier"] == root["id"])
                or (root["label"] == "ProductionFacility" and s["facility"] == root["id"])
                or (root["label"] == "Component" and s["component"] == root["id"]))

    def usable(record):
        return active(record, on) and record["approval"] == "approved"

    findings, gaps, alternatives = [], [], []
    base_evidence = [data["master_evidence"]] + ([disruption["evidence"]] if disruption else [])
    live_routes = [r for r in data["routes"] if usable(r) and r["role"] == "active"]
    exposed_sources = [s for s in data["sourcing"] if usable(s) and s["role"] == "active" and affected(s)]

    def add_finding(s, route):
        sku, vendor = (s or route)["sku"], (s or route)["vendor"]
        path = [root["id"]]
        if s:
            if path[-1] != s["facility"]:
                path.append(s["facility"])
            path.extend([s["id"], s["component"], vendor, sku])
        if route:
            if not s:
                path.extend([route["id"], vendor, sku, route["store"]])
            else:
                path.extend([route["id"], route["dc"], route["store"]])
        evidence = base_evidence + ([s.get("evidence")] if s else []) + ([route.get("evidence")] if route else [])
        supported = all(e in source_ids for e in evidence)
        record_ids = {r["id"] for r in (s, route) if r}
        dependency_edges = [e for e in graph_edges if e["start"] in record_ids
                            and e["type"] != "SUPPORTED_BY"]
        if s and root["label"] == "Supplier":
            dependency_edges += [e for e in graph_edges if e["start"] == root["id"]
                                 and e["type"] == "OPERATES" and e["end"] == s["facility"]]
        findings.append(dict(sku=sku, vendor=vendor, category=entities[sku]["category"],
                             sourcing_id=s["id"] if s else None, route_id=route["id"] if route else None,
                             dc=route["dc"] if route else None, store=route["store"] if route else None,
                             status="potential_exposure" if supported else "unverified_dependency",
                             path=path, evidence=sorted({e for e in evidence if e}),
                             dependency_edges=dependency_edges,
                             path_semantics="Ordered dependency explanation; inspect arrangement/route nodes for scoped edges."))
        if not supported:
            gaps.append(f"Missing evidence for dependency {s['id'] if s else route['id']}; exposure is unverified.")

    if root["label"] == "DC":
        exposed_routes = [r for r in live_routes if r["dc"] == root["id"]]
        for route in exposed_routes:
            add_finding(None, route)
            candidates = [r for r in data["routes"] if r["role"] == "backup" and usable(r)
                          and (r["sku"], r["vendor"], r["store"]) == (route["sku"], route["vendor"], route["store"])
                          and r["dc"] != root["id"] and r.get("evidence") in source_ids]
            for candidate in candidates:
                alternatives.append(dict(for_record=route["id"], record=candidate["id"],
                                         kind="route", destination=candidate["dc"], evidence=[candidate["evidence"]],
                                         limitation="Backup approval only; stock and transport capacity are unverified."))
            if not candidates:
                gaps.append(f"No documented approved backup route found for {route['id']}.")
    else:
        for s in exposed_sources:
            matched = [r for r in live_routes if (r["sku"], r["vendor"]) == (s["sku"], s["vendor"])]
            if not matched:
                add_finding(s, None)
                gaps.append(f"No active distribution route found for {s['sku']}/{s['vendor']}; downstream coverage unknown.")
            for route in matched:
                add_finding(s, route)
            candidates = [a for a in data["sourcing"] if a["role"] == "backup" and usable(a)
                          and (a["sku"], a["vendor"], a["component"]) == (s["sku"], s["vendor"], s["component"])
                          and not affected(a) and a.get("evidence") in source_ids]
            for candidate in candidates:
                alternatives.append(dict(for_record=s["id"], record=candidate["id"], kind="source",
                                         destination=candidate["facility"], evidence=[candidate["evidence"]],
                                         limitation="Approval for this dependency only; capacity and other required components are unverified."))
            if not candidates:
                gaps.append(f"No documented approved unaffected source found for {s['id']}.")
    summary = {key: sorted({f[key] for f in findings if f[key] and f["status"] == "potential_exposure"})
               for key in ("sku", "vendor", "category", "dc", "store")}
    used = {e for f in findings for e in f["evidence"]} | {e for a in alternatives for e in a["evidence"]}
    used.update(e for e in base_evidence if e)
    return dict(status="ok", synthetic=True, date=on, target={"id": root["id"], "name": root["name"]},
                scenario=disruption["id"] if disruption else "hypothetical single-target outage",
                summary=summary, findings=findings, alternatives=alternatives,
                coverage_gaps=sorted(set(gaps)),
                limitations=["Potential dependency exposure, not a forecast of shortages or lost sales.",
                             "Other disruption scenarios are not assumed to occur simultaneously.",
                             "Absence from the graph does not prove absence in the real supply chain.",
                             "All validity intervals are start-inclusive and end-exclusive."],
                names={id: e["name"] for id, e in entities.items()},
                evidence=[e for e in data["evidence"] if e["id"] in used])


def render_report(report):
    if report["status"] != "ok":
        import json
        return json.dumps(report, indent=2)
    names = report["names"]
    lines = [f"SYNTHETIC IMPACT REPORT: {report['target']['name']}", f"As of {report['date']}", ""]
    for key, values in report["summary"].items():
        lines.append(f"{key.upper()}: " + (", ".join(f"{v} ({names[v]})" for v in values) or "None documented"))
    lines.extend(["", "DEPENDENCY EXPLANATIONS (scoped by sourcing and route records)"])
    for f in report["findings"]:
        lines.append(f"[{f['status']}] " + " -> ".join(f["path"]) + " | Evidence: " + ", ".join(f["evidence"]))
    lines.extend(["", "DOCUMENTED ALTERNATIVES"])
    for a in report["alternatives"]:
        lines.append(f"{a['for_record']} -> {a['record']} ({a['destination']}): {a['limitation']} | {', '.join(a['evidence'])}")
    lines.extend(["", "COVERAGE GAPS", *report["coverage_gaps"], "", "LIMITATIONS", *report["limitations"], "", "SOURCES"])
    lines.extend(f"{e['id']}: {e['location']}" for e in report["evidence"])
    return "\n".join(lines) + "\n"
