"""Read a consistent, bounded graph snapshot; run optional analytics separately.

The current graph is small. Reading all scoped records once per user turn lets
the agent reuse the tested phase-one rules rather than maintain divergent logic.
This adapter intentionally rejects oversized snapshots instead of truncating.
"""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from neo4j import GraphDatabase, Query, unit_of_work

from ..graph_fixture import DEFAULT_DATA
from ..impact_analysis import validate

BUSINESS_LABELS = {"Supplier", "ProductionFacility", "Vendor", "Component", "SKU", "Category", "DC", "Store"}
RECORD_LABELS = BUSINESS_LABELS | {"SourcingArrangement", "DistributionRoute", "Disruption", "Evidence"}


def decode_graph(nodes, edges, default_date):
    by_id, typed = {}, {}
    for row in nodes:
        labels = set(row["labels"]) & RECORD_LABELS
        if len(labels) != 1:
            raise ValueError("Each Entity must have exactly one supported business label.")
        props = dict(row["props"])
        label = labels.pop()
        by_id[props["id"]] = props
        typed[props["id"]] = label
    outgoing, incoming = {}, {}
    for row in edges:
        outgoing.setdefault((row["start"], row["type"]), []).append(row["end"])
        incoming.setdefault((row["end"], row["type"]), []).append(row["start"])

    def one(id, relation, reverse=False, optional=False):
        values = (incoming if reverse else outgoing).get((id, relation), [])
        if optional and not values:
            return None
        if len(values) != 1:
            raise ValueError(f"Expected one {relation} relationship on {id}.")
        return values[0]

    data = dict(schema_version=1, synthetic=True, default_date=default_date,
                master_evidence="E-MASTER", entities=[], sourcing=[], routes=[], disruptions=[], evidence=[])
    for id, original in by_id.items():
        record, label = dict(original), typed[id]
        if label in BUSINESS_LABELS:
            record["label"] = label
            if label == "ProductionFacility":
                record.update(supplier=one(id, "OPERATES", reverse=True),
                              components=outgoing.get((id, "PRODUCES"), []))
            elif label == "SKU":
                route_ids = incoming.get((id, "FOR_SKU"), [])
                record.update(category=one(id, "IN_CATEGORY"),
                              components=outgoing.get((id, "REQUIRES_COMPONENT"), []),
                              vendors=incoming.get((id, "PROVIDES"), []),
                              dcs=sorted({one(r, "THROUGH_DC") for r in route_ids if typed[r] == "DistributionRoute"}))
            elif label == "Store":
                record.update(primary_dc=one(id, "SERVES", reverse=True),
                              backup_dc=one(id, "BACKUP_COVERAGE", reverse=True))
            data["entities"].append(record)
        elif label == "Evidence":
            data["evidence"].append(record)
        else:
            record["evidence"] = one(id, "SUPPORTED_BY", optional=True)
            if label == "SourcingArrangement":
                record.update(sku=one(id, "FOR_SKU"), vendor=one(id, "THROUGH_VENDOR"),
                              component=one(id, "FOR_COMPONENT"), facility=one(id, "FROM_FACILITY"))
                data["sourcing"].append(record)
            elif label == "DistributionRoute":
                record.update(sku=one(id, "FOR_SKU"), vendor=one(id, "FROM_VENDOR"),
                              dc=one(id, "THROUGH_DC"), store=one(id, "TO_STORE"))
                data["routes"].append(record)
            else:
                record.update(label=label, target=one(id, "AFFECTS"))
                data["disruptions"].append(record)
    checks = validate(data)
    if checks["errors"]:
        raise ValueError("Database graph failed integrity validation; run the graph checks before investigating.")
    return data


class FixtureRepository:
    def __init__(self, path=DEFAULT_DATA):
        self.data = json.loads(Path(path).read_text(encoding="utf-8"))

    def snapshot(self):
        return deepcopy(self.data)

    def close(self):
        pass


class Neo4jRepository:
    def __init__(self, settings):
        settings.require_database()
        self.settings = settings
        self.driver = GraphDatabase.driver(settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password.get_secret_value()), connection_timeout=20)

    def snapshot(self):
        @unit_of_work(timeout=self.settings.neo4j_query_timeout_seconds)
        def read(tx):
            nodes = tx.run("MATCH (n:Entity) RETURN labels(n) AS labels, properties(n) AS props LIMIT $limit",
                           limit=5001).data()
            edges = tx.run("MATCH (a:Entity)-[r]->(b:Entity) RETURN a.id AS start, type(r) AS type, b.id AS end LIMIT $limit",
                           limit=20001).data()
            if len(nodes) > 5000 or len(edges) > 20000:
                raise ValueError("Graph exceeds the prototype snapshot limit; scoped database queries are required.")
            if not nodes:
                raise ValueError("No Entity nodes found. Import the graph first.")
            return decode_graph(nodes, edges, self.settings.agent_default_date.isoformat())
        with self.driver.session(database=self.settings.neo4j_database, default_access_mode="READ") as session:
            return session.execute_read(read)

    def communities(self, on):
        if not self.settings.community_analytics_enabled:
            return {"status": "disabled", "message": "Enable COMMUNITY_ANALYTICS_ENABLED to allow billed Aura analytics sessions."}
        text = (Path(__file__).resolve().parents[2] / "neo4j_graph" / "communities.cypher").read_text(encoding="utf-8")
        project = text.split("// 2. Project", 1)[1].split("MATCH (s:SourcingArrangement)", 1)[1].split("// 3.", 1)[0]
        project = "MATCH (s:SourcingArrangement)" + project
        stream = text.split("CALL gds.leiden.stream", 1)[1].split("// 4.", 1)[0]
        stream = "CALL gds.leiden.stream" + stream
        graph_name = "agent-supply-" + uuid4().hex
        project = project.replace("'supply-communities-20261014'", "$graph_name").replace("minutes: 10", "minutes: $ttl")
        stream = stream.replace("'supply-communities-20261014'", "$graph_name")
        result = {"status": "error", "message": "Analytics did not complete."}
        with self.driver.session(database=self.settings.neo4j_database) as session:
            try:
                info = session.run(Query(project, timeout=120), graph_name=graph_name, on=on,
                                   ttl=self.settings.community_session_ttl_minutes).data()
                rows = session.run(Query(stream, timeout=120), graph_name=graph_name).data()
                result = dict(status="ok", date=on, projection=info, communities=rows,
                              limitations=["Active approved documented sourcing only; packaging excluded.",
                                           "Shared facilities, not causal impact or a risk score."])
            finally:
                try:
                    session.run("CALL gds.graph.drop($name, false)", name=graph_name).consume()
                except Exception:
                    result["cleanup_warning"] = "Could not confirm cleanup; check Aura Graph Analytics sessions. Inactivity TTL is configured."
        return result

    def close(self):
        self.driver.close()
