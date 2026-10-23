import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from supply_chain.agent.config import Settings, create_model
from supply_chain.agent.workflow import Answer, build_agent, turn_input


class OllamaTests(unittest.TestCase):
    def test_cloud_requires_its_own_key(self):
        settings = Settings(_env_file=None, llm_provider="ollama_cloud", llm_api_key="openai-key", ollama_api_key="")
        with self.assertRaisesRegex(ValueError, "OLLAMA_API_KEY"):
            create_model(settings)

    def test_cloud_sends_only_ollama_key_to_cloud(self):
        settings = Settings(_env_file=None, llm_provider="ollama_cloud", llm_model="gpt-oss:120b",
                            ollama_api_key="test-cloud-key", llm_api_key="openai-key",
                            ollama_base_url="http://localhost:11434")
        with patch("langchain_ollama.ChatOllama") as constructor:
            create_model(settings)
        options = constructor.call_args.kwargs
        self.assertEqual(options["base_url"], "https://ollama.com")
        self.assertEqual(options["client_kwargs"]["headers"]["Authorization"], "Bearer test-cloud-key")
        self.assertNotIn("num_ctx", options)
        self.assertNotIn("openai-key", str(options))

    def test_cloud_finalization_uses_tools_instead_of_enforced_schema(self):
        model = Mock()
        model.bind_tools.return_value.invoke.return_value = AIMessage(content="Which facility?")
        model.with_structured_output.return_value.invoke.return_value = Answer(
            status="clarification_required", summary="Which facility?", claims=[],
            limitations=[], next_checks=[], clarification_question="Which facility?")
        graph = build_agent(model, [], Settings(_env_file=None, llm_provider="ollama_cloud"))
        result = graph.invoke(turn_input("Investigate an outage"))
        model.with_structured_output.assert_called_once_with(Answer, method="function_calling")
        self.assertEqual(result["answer"]["status"], "clarification_required")

    def test_cloud_missing_report_fails_closed(self):
        model = Mock()
        model.bind_tools.return_value.invoke.return_value = AIMessage(content="Unsupported claim")
        model.with_structured_output.return_value.invoke.return_value = None
        graph = build_agent(model, [], Settings(_env_file=None, llm_provider="ollama_cloud"))
        with self.assertRaisesRegex(ValueError, "required structured report"):
            graph.invoke(turn_input("Investigate"))
        self.assertEqual(model.with_structured_output.return_value.invoke.call_count, 2)

    def test_cloud_retries_missing_report_once(self):
        model = Mock()
        model.bind_tools.return_value.invoke.return_value = AIMessage(content="Which facility?")
        report = Answer(status="clarification_required", summary="Which facility?", claims=[],
                        limitations=[], next_checks=[], clarification_question="Which facility?")
        model.with_structured_output.return_value.invoke.side_effect = [None, report]
        graph = build_agent(model, [], Settings(_env_file=None, llm_provider="ollama_cloud"))
        result = graph.invoke(turn_input("Investigate"))
        self.assertEqual(result["answer"]["status"], "clarification_required")
        self.assertEqual(model.with_structured_output.return_value.invoke.call_count, 2)

    def test_local_model_without_key_and_without_openai_endpoint(self):
        settings = Settings(_env_file=None, llm_provider="ollama", llm_model="qwen3:8b",
                            llm_api_key="", llm_base_url="https://example.invalid")
        model = create_model(settings)
        self.assertIsInstance(model, ChatOllama)
        self.assertEqual(model.base_url, "http://localhost:11434")
        self.assertEqual(model.num_ctx, 32768)
        self.assertFalse(model.reasoning)

    def test_ollama_workflow_uses_native_schema_and_no_openai_tool_options(self):
        settings = Settings(_env_file=None, llm_provider="ollama")
        model = Mock()
        model.bind_tools.return_value.invoke.return_value = AIMessage(content="Please specify a target")
        model.with_structured_output.return_value.invoke.return_value = Answer(
            status="clarification_required", summary="Which facility?", claims=[],
            limitations=[], next_checks=[], clarification_question="Which facility?")
        result = build_agent(model, [], settings).invoke(turn_input("Investigate an outage"))
        model.bind_tools.assert_called_once_with([])
        model.with_structured_output.assert_called_once_with(Answer, method="json_schema")
        self.assertEqual(result["answer"]["status"], "clarification_required")
