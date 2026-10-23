from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from supply_chain.agent.config import Settings
from supply_chain.agent.chat import user_error
from supply_chain.agent.errors import classify_api_error

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


class ChatUITests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, llm_api_key="test-only", neo4j_uri="neo4j://example.invalid",
                                 neo4j_password="test-only")
        self.patch = patch("supply_chain.agent.config.Settings", return_value=self.settings)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_page_loads_without_api_calls(self):
        app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Supply Chain Investigator")
        self.assertEqual(len(app.chat_input), 1)
        self.assertEqual(app.session_state["chat_entries"], [])

    def test_chat_followup_and_new_conversation(self):
        response = dict(answer={"summary": "Basic Tee is potentially exposed.", "claims": [],
                               "clarification_question": "", "limitations": [], "next_checks": []},
                        messages=["history-marker"], sources=[], checks=2, date="2026-10-14", backend="Neo4j")
        with patch("supply_chain.agent.chat.run_chat_turn", side_effect=lambda *a, **k: dict(response)) as run:
            app = AppTest.from_file(str(APP)).run()
            app.chat_input[0].set_value("What depends on Apex East?").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 2)
            app.chat_input[0].set_value("Which alternatives exist?").run()
            self.assertEqual(run.call_args.args[1], ["history-marker"])
            self.assertEqual(len(app.session_state["chat_entries"]), 4)
            next(b for b in app.button if b.label == "New conversation").click().run()
            self.assertEqual(app.session_state["chat_entries"], [])
            self.assertEqual(app.session_state["agent_messages"], [])

    def test_failure_does_not_commit_model_history_or_expose_secrets(self):
        with patch("supply_chain.agent.chat.run_chat_turn", side_effect=RuntimeError("private-api-key")):
            app = AppTest.from_file(str(APP)).run()
            app.chat_input[0].set_value("Investigate Apex East").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["agent_messages"], [])
            self.assertTrue(app.error)
            self.assertNotIn("private-api-key", app.error[0].value)

    def test_missing_key_disables_chat(self):
        self.settings.llm_api_key = self.settings.llm_api_key.__class__("")
        app = AppTest.from_file(str(APP)).run()
        self.assertTrue(app.chat_input[0].disabled)

    def test_cloud_requires_ollama_key_even_with_openai_key(self):
        self.settings.llm_provider = "ollama_cloud"
        self.settings.ollama_api_key = self.settings.ollama_api_key.__class__("")
        app = AppTest.from_file(str(APP)).run()
        self.assertTrue(app.chat_input[0].disabled)
        self.assertIn("OLLAMA_API_KEY", app.warning[0].value)
        self.settings.ollama_api_key = self.settings.ollama_api_key.__class__("test-only")
        app.run()
        self.assertFalse(app.chat_input[0].disabled)

    def test_ollama_chat_does_not_require_api_key(self):
        self.settings.llm_provider = "ollama"
        self.settings.llm_model = "qwen3:8b"
        self.settings.llm_api_key = self.settings.llm_api_key.__class__("")
        app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.chat_input[0].disabled)

    def test_missing_ollama_model_has_safe_actionable_error(self):
        from ollama import ResponseError
        message = user_error(ResponseError("private server detail", status_code=404))
        self.assertIn("ollama pull", message)
        self.assertNotIn("private server detail", message)

    def test_backend_change_resets_conversation(self):
        app = AppTest.from_file(str(APP)).run()
        app.session_state["chat_entries"] = [{"role": "user", "content": "old question"}]
        app.selectbox[0].set_value("Local sample").run()
        self.assertEqual(app.session_state["chat_entries"], [])

    def test_quota_error_is_actionable(self):
        error = type("OpenAIRateLimitError", (Exception,), {})("private details")
        self.assertIn("billing", user_error(error))
        self.assertNotIn("private details", user_error(error))

    def test_nested_quota_body_is_classified(self):
        error = RuntimeError("private details")
        error.body = {"error": {"type": "insufficient_quota", "code": "insufficient_quota", "message": "secret"}}
        self.assertEqual(classify_api_error(error)["kind"], "quota")
        self.assertIn("Waiting or resending", user_error(error))
        self.assertNotIn("secret", user_error(error))

    def test_wrapped_rate_error(self):
        cause = RuntimeError("private details")
        cause.code = "rate_limit_exceeded"
        error = RuntimeError("wrapper")
        error.__cause__ = cause
        self.assertEqual(classify_api_error(error)["kind"], "rate")
        self.assertIn("temporary", user_error(error))

    def test_unknown_error_metadata_is_not_exposed(self):
        error = RuntimeError("private details")
        error.body = {"code": "secret-token", "type": "secret-value"}
        self.assertEqual(classify_api_error(error), {"kind": "unknown", "codes": []})


if __name__ == "__main__":
    unittest.main()
