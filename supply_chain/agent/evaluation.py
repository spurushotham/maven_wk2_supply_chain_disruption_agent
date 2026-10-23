"""Graph regression evaluation without any model calls."""
from ..impact_analysis import investigate


def evaluate_graph(data):
    results = []
    expected = {
        "D-01": ["A01", "A02", "A03", "B01", "B02", "B04", "F01", "F02", "F03"],
        "D-02": ["A01", "A02", "A03", "A04", "B01", "B02", "B03", "B04", "F01", "F02", "F03", "F04"],
        "D-03": ["A01", "A02", "A03", "B01", "B02", "B04", "F01", "F03"],
        "D-04": ["A03", "A04", "B01", "B03", "F02"],
    }
    reports = {target: investigate(data, target, "2026-10-14") for target in expected}
    for target, skus in expected.items():
        actual = reports[target].get("summary", {}).get("sku", [])
        results.append(dict(case=f"{target}: supported SKUs", passed=actual == skus, expected=skus, actual=actual))
    a01 = [f for f in reports["D-01"]["findings"] if f["sku"] == "A01"]
    checks = {
        "A01 vendor-specific sourcing": {f["vendor"] for f in a01} == {"V-NA"},
        "A01 scoped store routes": {f["store"] for f in a01} == {"ST-BOS", "ST-CHI", "ST-DAL"},
        "Supplier outage excludes Apex West fallback": not reports["D-02"]["alternatives"],
        "East DC only affects Boston and NYC": reports["D-03"]["summary"]["store"] == ["ST-BOS", "ST-NYC"],
        "East DC has six approved route backups": len(reports["D-03"]["alternatives"]) == 6,
        "Travel Bag zipper evidence is unverified": any(f["sku"] == "B04" and f["status"] == "unverified_dependency"
                                                        for f in reports["D-04"]["findings"]),
    }
    results += [{"case": case, "passed": passed} for case, passed in checks.items()]
    return {"status": "passed" if all(r["passed"] for r in results) else "failed", "cases": results,
            "scope": "Deterministic graph retrieval checks; not LLM answer-quality evaluation."}
