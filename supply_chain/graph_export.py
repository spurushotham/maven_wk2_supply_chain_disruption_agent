"""Translate the fixture into a portable Neo4j property graph."""
import json
from pathlib import Path


def graph_records(data):
    nodes, edges = [], []
    master = data["master_evidence"]

    def edge(start, kind, end, evidence=master):
        edges.append(dict(start=start, type=kind, end=end, evidence=evidence))

    for entity in data["entities"]:
        id, label = entity["id"], entity["label"]
        nodes.append(dict(id=id, label=label, name=entity["name"], synthetic=True))
        edge(id, "SUPPORTED_BY", master)
        if label == "ProductionFacility":
            edge(entity["supplier"], "OPERATES", id)
            for component in entity["components"]:
                edge(id, "PRODUCES", component)
        if label == "SKU":
            edge(id, "IN_CATEGORY", entity["category"])
            for component in entity["components"]:
                edge(id, "REQUIRES_COMPONENT", component)
            for vendor in entity["vendors"]:
                edge(vendor, "PROVIDES", id)
        if label == "Store":
            edge(entity["primary_dc"], "SERVES", id)
            edge(entity["backup_dc"], "BACKUP_COVERAGE", id)
    for key, label, mapping in [
        ("sourcing", "SourcingArrangement", {"sku": "FOR_SKU", "vendor": "THROUGH_VENDOR",
                                            "component": "FOR_COMPONENT", "facility": "FROM_FACILITY"}),
        ("routes", "DistributionRoute", {"sku": "FOR_SKU", "vendor": "FROM_VENDOR", "dc": "THROUGH_DC", "store": "TO_STORE"}),
        ("disruptions", "Disruption", {"target": "AFFECTS"}),
    ]:
        for record in data[key]:
            props = {k: v for k, v in record.items() if k not in mapping and k != "label" and v is not None}
            nodes.append(dict(props, label=label, synthetic=True))
            for field, relation in mapping.items():
                edge(record["id"], relation, record[field], record.get("evidence"))
            if record.get("evidence"):
                edge(record["id"], "SUPPORTED_BY", record["evidence"], record["evidence"])
    for record in data["evidence"]:
        nodes.append(dict(record, label="Evidence"))
    # Store assortment is derived only from scoped routes, never generic DC coverage.
    for store, sku in sorted({(r["store"], r["sku"]) for r in data["routes"]}):
        edge(store, "CARRIES", sku)
    return nodes, edges


def literal(value):
    if isinstance(value, dict):
        return "{" + ", ".join(f"`{k}`: {literal(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(literal(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=True)


def export_neo4j(data, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    nodes, edges = graph_records(data)
    statements = ["// SYNTHETIC DEMO: import into a dedicated database. No APOC or plugins required.",
                  "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;"]
    for node in nodes:
        props = {k: v for k, v in node.items() if k != "label"}
        statements.append(f"MERGE (n:Entity {{id: {literal(node['id'])}}}) SET n:{node['label']} SET n += {literal(props)};")
    for edge in edges:
        statements.append(f"MATCH (a:Entity {{id: {literal(edge['start'])}}}), (b:Entity {{id: {literal(edge['end'])}}}) "
                          f"MERGE (a)-[r:{edge['type']}]->(b) SET r.evidence = {literal(edge['evidence'])};")
    (directory / "import.cypher").write_text("\n".join(statements) + "\n", encoding="utf-8")
    return {"nodes": len(nodes), "relationships": len(edges), "output": str(directory)}
