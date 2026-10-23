# /// script
# requires-python = ">=3.11"
# dependencies = ["neo4j>=6,<7"]
# ///
"""Run this project's generated, one-statement-per-line Cypher using uv."""
import argparse
import getpass
import os
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "neo4j_graph" / "import.cypher"


def read_statements(path):
    """The project exporter emits one complete statement per physical line.

    Do not split on semicolons: evidence strings may themselves contain them.
    This is deliberately not a general-purpose Cypher script parser.
    """
    statements = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if not line.endswith(";"):
            raise ValueError(f"Line {number}: expected one complete semicolon-terminated statement.")
        statements.append(line[:-1])
    if not statements:
        raise ValueError("The import file contains no statements.")
    return statements


def execute_batch(tx, statements):
    for statement in statements:
        tx.run(statement).consume()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI"))
    parser.add_argument("--username", default=os.getenv("NEO4J_USERNAME", "neo4j"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--check-file", action="store_true", help="Validate the local file without connecting")
    args = parser.parse_args()
    try:
        statements = read_statements(args.file)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Import file error: {exc}\n")
    if args.check_file:
        print(f"Validated {len(statements)} single-line statements; no database connection made.")
        return
    uri = args.uri or input("Neo4j connection URI: ").strip()
    if not uri:
        parser.error("A connection URI is required.")
    try:
        from neo4j import GraphDatabase
    except ImportError:
        parser.exit(1, "Run with: python -m uv run scripts/import_graph.py\n")
    password = os.getenv("NEO4J_PASSWORD") or getpass.getpass("Database password (hidden): ")
    completed = 0
    try:
        with GraphDatabase.driver(uri, auth=(args.username, password), connection_timeout=30) as driver:
            driver.verify_connectivity()
            print(f"Connected. Importing {len(statements)} statements into {args.database}.", flush=True)
            with driver.session(database=args.database) as session:
                # Schema and data writes must be in separate transactions.
                schema = [s for s in statements if s.startswith("CREATE CONSTRAINT ")]
                data = [s for s in statements if not s.startswith("CREATE CONSTRAINT ")]
                for statement in schema:
                    session.run(statement).consume()
                    completed += 1
                for offset in range(0, len(data), 100):
                    batch = data[offset:offset + 100]
                    session.execute_write(execute_batch, batch)
                    completed += len(batch)
                    print(f"Committed {completed}/{len(statements)} statements.", flush=True)
                nodes = session.run("MATCH (n:Entity) RETURN count(n) AS count").single()["count"]
                edges = session.run("MATCH (:Entity)-[r]->(:Entity) RETURN count(r) AS count").single()["count"]
                print(f"Import complete. Database totals: {nodes} Entity nodes, {edges} relationships.")
                print("Expected on an empty demo database: 369 nodes and 1000 relationships.")
    except Exception as exc:
        # Do not print exception details that might contain connection credentials.
        parser.exit(1, f"Import failed ({type(exc).__name__}); {completed} statements committed. "
                    "Check the URI, database name, database password, network, and write permissions. "
                    "Previously committed batches remain; rerunning this generated MERGE script is supported.\n")


if __name__ == "__main__":
    main()
