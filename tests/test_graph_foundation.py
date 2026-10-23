"""Known-answer tests: expectations are explicit scenario business rules."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from supply_chain.impact_analysis import active, investigate, resolve_entity, validate
from supply_chain.graph_fixture import build_scenario, DEFAULT_DATA
from supply_chain.graph_export import export_neo4j, graph_records


class PhaseOneTests(unittest.TestCase):
    def setUp(self):
        self.data = build_scenario()

    def test_fixture_is_valid_with_one_intentional_gap(self):
        result = validate(self.data)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("SA-067", result["warnings"][0])

    def test_business_entity_count(self):
        self.assertEqual(len(self.data["entities"]) + len(self.data["disruptions"]), 53)
        self.assertEqual(sum(e["label"] == "SKU" for e in self.data["entities"]), 12)

    def test_checked_in_fixture_matches_generator(self):
        self.assertEqual(json.loads(DEFAULT_DATA.read_text(encoding="utf-8")), self.data)

    def test_facility_expected_skus_and_stores(self):
        report = investigate(self.data, "D-01")
        self.assertEqual(report["summary"]["sku"], ["A01", "A02", "A03", "B01", "B02", "B04", "F01", "F02", "F03"])
        self.assertEqual(report["summary"]["store"], ["ST-ATL", "ST-BOS", "ST-CHI", "ST-DAL", "ST-LA", "ST-MIN", "ST-NYC", "ST-SEA"])
        self.assertEqual(report["summary"]["category"], ["CAT-APP", "CAT-BAG", "CAT-FOOT"])

    def test_same_sku_different_vendor_not_overflagged(self):
        rows = [f for f in investigate(self.data, "D-01")["findings"] if f["sku"] == "A01"]
        self.assertEqual({f["vendor"] for f in rows}, {"V-NA"})
        self.assertEqual({f["store"] for f in rows}, {"ST-BOS", "ST-CHI", "ST-DAL"})

    def test_supplier_outage_expands_to_west_facility(self):
        report = investigate(self.data, "D-02")
        self.assertEqual(len(report["summary"]["sku"]), 12)
        self.assertTrue(any(f["sku"] == "A01" and f["vendor"] == "V-EE" for f in report["findings"]))

    def test_supplier_outage_excludes_same_supplier_backups(self):
        self.assertEqual(investigate(self.data, "D-02")["alternatives"], [])
        self.assertTrue(investigate(self.data, "D-01")["alternatives"])

    def test_dc_outage_is_regional(self):
        report = investigate(self.data, "D-03")
        self.assertEqual(report["summary"]["store"], ["ST-BOS", "ST-NYC"])
        self.assertEqual(report["summary"]["dc"], ["DC-E"])
        self.assertEqual(report["summary"]["sku"], ["A01", "A02", "A03", "B01", "B02", "B04", "F01", "F03"])
        self.assertEqual({a["destination"] for a in report["alternatives"]}, {"DC-C"})
        self.assertEqual(len(report["alternatives"]), 6)

    def test_component_hold_missing_evidence_is_not_confirmed_exposure(self):
        report = investigate(self.data, "D-04")
        self.assertEqual(report["summary"]["sku"], ["A03", "A04", "B01", "B03", "F02"])
        unverified = [f for f in report["findings"] if f["sku"] == "B04"]
        self.assertTrue(unverified)
        self.assertTrue(all(f["status"] == "unverified_dependency" for f in unverified))
        self.assertEqual(report["alternatives"], [])

    def test_pending_approval_is_not_an_alternative(self):
        report = investigate(self.data, "FAC-SN")
        self.assertEqual(report["summary"]["sku"], ["F01", "F03"])
        sources = {s["id"]: s for s in self.data["sourcing"]}
        self.assertEqual({sources[a["record"]]["vendor"] for a in report["alternatives"]}, {"V-UC"})
        self.assertTrue(any("No documented approved" in g for g in report["coverage_gaps"]))

    def test_date_intervals_are_half_open(self):
        record = {"valid_from": "2026-01-01", "valid_to": "2027-01-01"}
        self.assertTrue(active(record, "2026-01-01"))
        self.assertFalse(active(record, "2027-01-01"))

    def test_historical_sourcing_and_missing_downstream_coverage(self):
        report = investigate(self.data, "FAC-AE", "2025-06-01")
        self.assertEqual(report["summary"]["sku"], ["A01"])
        self.assertEqual(report["summary"]["vendor"], ["V-EE"])
        self.assertEqual(report["summary"]["store"], [])
        self.assertTrue(any("downstream coverage unknown" in g for g in report["coverage_gaps"]))

    def test_disruption_outside_window(self):
        self.assertEqual(investigate(self.data, "D-01", "2026-11-01")["status"], "outside_disruption_window")

    def test_entity_resolution_unknown_ambiguous_and_exact(self):
        self.assertEqual(investigate(self.data, "Apex")["status"], "clarification_required")
        self.assertEqual(investigate(self.data, "Unknown Company")["status"], "not_found")
        self.assertEqual(resolve_entity(self.data, "apex east")[0]["id"], "FAC-AE")

    def test_unsupported_target(self):
        self.assertEqual(investigate(self.data, "A01")["status"], "unsupported_target")

    def test_expired_routes_dont_prove_no_impact(self):
        data = copy.deepcopy(self.data)
        for route in data["routes"]:
            route["valid_to"] = "2026-02-01"
        report = investigate(data, "D-01")
        self.assertTrue(report["summary"]["sku"])
        self.assertEqual(report["summary"]["store"], [])
        self.assertTrue(report["coverage_gaps"])

    def test_dependency_edges_and_evidence_exist(self):
        _, edges = graph_records(self.data)
        edge_set = {(e["start"], e["type"], e["end"]) for e in edges}
        evidence = {e["id"] for e in self.data["evidence"]}
        for target in ["D-01", "D-02", "D-03", "D-04"]:
            for finding in investigate(self.data, target)["findings"]:
                self.assertTrue(set(finding["evidence"]) <= evidence)
                self.assertTrue(finding["dependency_edges"])
                for edge in finding["dependency_edges"]:
                    self.assertIn((edge["start"], edge["type"], edge["end"]), edge_set)

    def test_validation_rejects_corruption(self):
        for mutate in [lambda d: d["entities"].append(d["entities"][0]),
                       lambda d: d["sourcing"][0].update(vendor="V-BAD"),
                       lambda d: d["sourcing"][0].update(valid_to="2020-01-01"),
                       lambda d: d["sourcing"][0].update(evidence="E-MISSING"),
                       lambda d: d["sourcing"][0].update(component="C-MZ")]:
            with self.subTest(mutation=mutate):
                data = copy.deepcopy(self.data)
                mutate(data)
                self.assertTrue(validate(data)["errors"])

    def test_export_is_repeatable_and_has_no_dangling_edges(self):
        nodes, edges = graph_records(self.data)
        ids = {n["id"] for n in nodes}
        self.assertEqual(len(ids), len(nodes))
        self.assertTrue(all(e["start"] in ids and e["end"] in ids for e in edges))
        with tempfile.TemporaryDirectory() as tmp:
            export_neo4j(self.data, tmp)
            first = (Path(tmp) / "import.cypher").read_text(encoding="utf-8")
            export_neo4j(self.data, tmp)
            self.assertEqual(first, (Path(tmp) / "import.cypher").read_text(encoding="utf-8"))
            self.assertEqual({p.name for p in Path(tmp).iterdir()}, {"import.cypher"})
            self.assertIn("MERGE", first)
            self.assertNotIn("DELETE", first)

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            investigate(self.data, "D-01", "not-a-date")



if __name__ == "__main__":
    unittest.main()
