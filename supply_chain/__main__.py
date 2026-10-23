import argparse
import json
from pathlib import Path

from .impact_analysis import investigate, render_report, validate
from .graph_fixture import DEFAULT_DATA, ROOT, write_fixture
from .graph_export import export_neo4j


def main():
    parser = argparse.ArgumentParser(description="Synthetic supply chain impact tools (no LLM required)")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate", help="Rebuild the deterministic synthetic fixture and source documents")
    commands.add_parser("validate", help="Validate records and report evidence coverage gaps")
    export = commands.add_parser("export", help="Write the idempotent Neo4j Cypher import script")
    export.add_argument("--output", type=Path, default=ROOT / "neo4j_graph")
    impact = commands.add_parser("investigate")
    impact.add_argument("target", help="Entity/disruption ID or unambiguous name")
    impact.add_argument("--date", help="YYYY-MM-DD; defaults to fixture investigation date")
    impact.add_argument("--format", choices=["text", "json"], default="text")
    impact.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            data = write_fixture(args.data)
            print(f"Created {args.data}; {len(data['entities']) + len(data['disruptions'])} business entities")
            return 0
        data = json.loads(args.data.read_text(encoding="utf-8"))
        checks = validate(data)
        if args.command == "validate" or checks["errors"]:
            print(json.dumps(checks, indent=2))
            return 1 if checks["errors"] else 0
        if args.command == "export":
            print(json.dumps(export_neo4j(data, args.output), indent=2))
            return 0
        report = investigate(data, args.target, args.date)
        output = json.dumps(report, indent=2) + "\n" if args.format == "json" else render_report(report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(output, end="")
        return 0 if report["status"] == "ok" else 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
