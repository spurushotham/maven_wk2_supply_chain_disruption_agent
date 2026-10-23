import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location("import_graph", Path(__file__).resolve().parents[1] / "scripts" / "import_graph.py")
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class ImportScriptTests(unittest.TestCase):
    def test_generated_file_has_expected_statement_count(self):
        statements = importer.read_statements(importer.DEFAULT_FILE)
        self.assertEqual(len(statements), 1370)
        self.assertTrue(statements[0].startswith("CREATE CONSTRAINT"))

    def test_semicolon_inside_string_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.cypher"
            path.write_text('// comment\nMERGE (n {text: "a; b"});\n', encoding="utf-8")
            self.assertEqual(importer.read_statements(path), ['MERGE (n {text: "a; b"})'])

    def test_incomplete_statement_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.cypher"
            path.write_text("MERGE (n)\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                importer.read_statements(path)

    def test_batch_consumes_results_and_propagates_failure(self):
        tx = Mock()
        importer.execute_batch(tx, ["one", "two"])
        self.assertEqual(tx.run.call_count, 2)
        self.assertEqual(tx.run.return_value.consume.call_count, 2)
        tx.run.side_effect = RuntimeError("failed")
        with self.assertRaises(RuntimeError):
            importer.execute_batch(tx, ["one", "two"])
