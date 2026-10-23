"""Create a deterministic, explicitly synthetic scenario; no LLM extraction."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "scenario.json"


def build_scenario():
    entities, evidence, arrangements, routes = [], [], [], []

    def entity(id, label, name, **props):
        entities.append(dict(id=id, label=label, name=name, **props))

    def source(id, title, text):
        evidence.append(dict(id=id, title=title, text=text, recorded_at="2026-01-01",
                             synthetic=True, location=f"data/evidence/{id}.md"))
        return id

    master = source("E-MASTER", "Synthetic master register",
                    "The scenario's entity register defines ownership, production capabilities, "
                    "product component requirements, vendor approvals, and store assortment. "
                    "All records are fictional; component lists are intentionally simplified.")
    for id, name in [("SUP-AP", "Apex Textiles"), ("SUP-SM", "Summit Materials"),
                     ("SUP-FC", "Flex Components"), ("SUP-HP", "Harbor Packaging")]:
        entity(id, "Supplier", name)
    for id, name, supplier, components in [
        ("FAC-AE", "Apex East", "SUP-AP", ["C-CT", "C-TF"]),
        ("FAC-AW", "Apex West", "SUP-AP", ["C-CT", "C-RF"]),
        ("FAC-SN", "Summit North", "SUP-SM", ["C-RS", "C-FI"]),
        ("FAC-SS", "Summit South", "SUP-SM", ["C-RS", "C-BK"]),
        ("FAC-FP", "Flex Plant", "SUP-FC", ["C-MZ", "C-BK", "C-FI"]),
        ("FAC-HP", "Harbor Plant", "SUP-HP", ["C-SC"]),
    ]:
        entity(id, "ProductionFacility", name, supplier=supplier, components=components)
    for id, name in [("V-NA", "Northstar Apparel"), ("V-TW", "TrailWorks"),
                     ("V-UC", "UrbanCarry"), ("V-EE", "Everyday Essentials")]:
        entity(id, "Vendor", name)
    for id, name in [("CT", "Cotton Fabric"), ("TF", "Technical Fabric"),
                     ("RF", "Recycled Fabric"), ("RS", "Rubber Sole"),
                     ("FI", "Foam Insole"), ("MZ", "Metal Zipper"),
                     ("BK", "Buckle"), ("SC", "Shipping Carton")]:
        entity(f"C-{id}", "Component", name)
    for id, name in [("APP", "Apparel"), ("FOOT", "Footwear"), ("BAG", "Bags")]:
        entity(f"CAT-{id}", "Category", name)
    for id, name in [("E", "East"), ("C", "Central"), ("S", "South"), ("W", "West")]:
        entity(f"DC-{id}", "DC", f"{name} DC")
    for id, name, dc, backup in [
        ("BOS", "Boston", "E", "C"), ("NYC", "NYC", "E", "C"),
        ("CHI", "Chicago", "C", "E"), ("MIN", "Minneapolis", "C", "E"),
        ("DAL", "Dallas", "S", "C"), ("ATL", "Atlanta", "S", "C"),
        ("SEA", "Seattle", "W", "S"), ("LA", "Los Angeles", "W", "S"),
    ]:
        entity(f"ST-{id}", "Store", name, primary_dc=f"DC-{dc}", backup_dc=f"DC-{backup}")
    products = [
        ("A01", "Basic Tee", "APP", ["NA", "EE"], ["CT"], "ECS"),
        ("A02", "Polo", "APP", ["NA"], ["CT"], "ES"),
        ("A03", "Rain Jacket", "APP", ["NA", "TW"], ["TF", "MZ"], "EW"),
        ("A04", "Fleece Jacket", "APP", ["TW", "EE"], ["RF", "MZ"], "CW"),
        ("F01", "Running Shoe", "FOOT", ["TW", "EE"], ["TF", "RS", "FI"], "ECSW"),
        ("F02", "Hiking Boot", "FOOT", ["TW"], ["TF", "RS", "MZ"], "CW"),
        ("F03", "Casual Sneaker", "FOOT", ["UC", "EE"], ["CT", "RS", "FI"], "ESW"),
        ("F04", "Slip-on Shoe", "FOOT", ["EE"], ["RF", "RS"], "CS"),
        ("B01", "Backpack", "BAG", ["UC", "TW"], ["TF", "MZ", "BK"], "ECSW"),
        ("B02", "Tote", "BAG", ["UC", "EE"], ["CT"], "ES"),
        ("B03", "Duffel", "BAG", ["UC", "NA"], ["RF", "MZ"], "CW"),
        ("B04", "Travel Bag", "BAG", ["UC"], ["TF", "MZ", "BK"], "EW"),
    ]
    for sku, name, cat, vendors, components, dcs in products:
        entity(sku, "SKU", name, category=f"CAT-{cat}",
               vendors=[f"V-{v}" for v in vendors],
               components=[f"C-{c}" for c in components + ["SC"]],
               dcs=[f"DC-{d}" for d in dcs])

    def arrangement(sku, vendor, component, facility, role="active", approval="approved",
                    start="2026-01-01", end="2027-01-01", evidence_present=True):
        id = f"SA-{len(arrangements)+1:03d}"
        record = dict(id=id, sku=sku, vendor=vendor, component=component, facility=facility,
                      role=role, approval=approval, valid_from=start, valid_to=end)
        record["evidence"] = source(f"E-{id}", f"Sourcing record {id}",
                                   json.dumps(record, sort_keys=True)) if evidence_present else None
        arrangements.append(record)

    for sku in [e for e in entities if e["label"] == "SKU"]:
        for vendor in sku["vendors"]:
            for component in sku["components"]:
                facility = {"C-CT": "FAC-AW" if vendor == "V-EE" else "FAC-AE",
                            "C-TF": "FAC-AE", "C-RF": "FAC-AW", "C-RS": "FAC-SS",
                            "C-FI": "FAC-FP" if vendor == "V-EE" else "FAC-SN",
                            "C-MZ": "FAC-FP", "C-BK": "FAC-SS", "C-SC": "FAC-HP"}[component]
                # A deliberate gap: source record unavailable for this one dependency.
                documented = not (sku["id"] == "B04" and component == "C-MZ")
                arrangement(sku["id"], vendor, component, facility, evidence_present=documented)
                if component == "C-CT" and facility == "FAC-AE":
                    arrangement(sku["id"], vendor, component, "FAC-AW", "backup")
                if component == "C-FI" and facility == "FAC-SN":
                    approval = "pending" if vendor == "V-TW" else "approved"
                    arrangement(sku["id"], vendor, component, "FAC-FP", "backup", approval)
    arrangement("A01", "V-EE", "C-CT", "FAC-AE", start="2025-01-01", end="2026-01-01")

    stores = [e for e in entities if e["label"] == "Store"]
    for sku in [e for e in entities if e["label"] == "SKU"]:
        for index, store in enumerate(stores):
            if store["primary_dc"] not in sku["dcs"]:
                continue
            vendor = sku["vendors"][index % len(sku["vendors"])]
            for role, dc in [("active", store["primary_dc"]), ("backup", store["backup_dc"])]:
                if role == "backup" and dc not in sku["dcs"]:
                    continue
                id = f"DR-{len(routes)+1:03d}"
                record = dict(id=id, sku=sku["id"], vendor=vendor, dc=dc, store=store["id"],
                              role=role, approval="approved", valid_from="2026-01-01",
                              valid_to="2027-01-01")
                record["evidence"] = source(f"E-{id}", f"Distribution record {id}",
                                           json.dumps(record, sort_keys=True))
                routes.append(record)
    disruptions = []
    for id, name, target in [("D-01", "Apex East shutdown", "FAC-AE"),
                             ("D-02", "Apex supplier outage", "SUP-AP"),
                             ("D-03", "East DC closure", "DC-E"),
                             ("D-04", "Metal Zipper component-wide quality hold", "C-MZ")]:
        ev = source(f"E-{id}", name, f"Hypothetical scenario: {target} unavailable from 2026-10-01 "
                    "through 2026-10-31. These are independent scenarios, not simultaneous events.")
        disruptions.append(dict(id=id, label="Disruption", name=name, target=target,
                                valid_from="2026-10-01", valid_to="2026-11-01", evidence=ev))
    return dict(schema_version=1, synthetic=True, default_date="2026-10-14",
                master_evidence=master, entities=entities, sourcing=arrangements,
                routes=routes, disruptions=disruptions, evidence=evidence)


def write_fixture(path=DEFAULT_DATA):
    data = build_scenario()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    evidence_dir = path.parent / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    for record in data["evidence"]:
        (evidence_dir / f"{record['id']}.md").write_text(
            f"# {record['title']}\n\nSYNTHETIC — not operational evidence.\n\n"
            f"Recorded: {record['recorded_at']}\n\n{record['text']}\n", encoding="utf-8")
    return data
