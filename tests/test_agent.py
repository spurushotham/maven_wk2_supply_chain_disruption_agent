"""Offline agent tests use real LangGraph/typed tools and a scripted model."""
import json
import unittest
from unittest.mock import Mock

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from supply_chain.agent.config import Settings
from supply_chain.agent.evaluation import evaluate_graph
from supply_chain.agent.repository import FixtureRepository, decode_graph
from supply_chain.agent.tools import InvestigationService, build_tools
from supply_chain.agent.workflow import Answer, Claim, build_agent, turn_input, validate_answer
from supply_chain.graph_export import graph_records
from supply_chain.graph_fixture import build_scenario
from supply_chain.impact_analysis import investigate


class ScriptedModel:
    def __init__(self, messages, answer):
        self.messages = iter(messages)
        self.answer = answer

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages):
        return next(self.messages)

    def with_structured_output(self, schema):
        stub = Mock()
        stub.invoke.return_value = self.answer
        return stub


def response(name, args, id="call-1"):
    return AIMessage(content="", tool_calls=[{"id": id, "name": name, "args": args, "type": "tool_call"}])


class AgentTests(unittest.TestCase):
    def test_followup_without_retrieval_is_redirected_to_graph(self):
        answer = Answer(status="answered", summary="Apex East resolved.",
                        claims=[Claim(text="Apex East is the target.", entity_ids=["FAC-AE"], evidence_ids=["E-MASTER"])],
                        limitations=[], next_checks=[], clarification_question="")
        model = ScriptedModel([AIMessage(content="I remember the previous findings."),
                               response("resolve_entity_tool", {"name_or_id": "FAC-AE"}),
                               AIMessage(content="Resolved")], answer)
        formatter = Mock()
        formatter.invoke.return_value = answer
        model.with_structured_output = Mock(return_value=formatter)
        state = turn_input("Which SKUs will be impacted if the apex east location is affected?")
        state["messages"] = [HumanMessage(content="OLD_QUESTION"), AIMessage(content="OLD_EVIDENCE"), *state["messages"]]
        result = build_agent(model, self.tools, self.settings).invoke(state)
        self.assertEqual(result["tool_calls_used"], 1)
        self.assertEqual(result["answer"]["status"], "answered")
        final_context = str(formatter.invoke.call_args.args[0])
        self.assertNotIn("OLD_EVIDENCE", final_context)
        self.assertNotIn("OLD_QUESTION", final_context)

    def setUp(self):
        self.settings = Settings(_env_file=None, agent_max_tool_calls=3)
        self.service = InvestigationService(FixtureRepository())
        self.service.refresh()
        self.tools = build_tools(self.service)
        self.by_name = {t.name: t for t in self.tools}

    def test_snapshot_roundtrip_preserves_scenario_answers(self):
        original = build_scenario()
        nodes, edges = graph_records(original)
        rows = [{"labels": ["Entity", n["label"]], "props": {k: v for k, v in n.items() if k != "label"}} for n in nodes]
        decoded = decode_graph(rows, edges, "2026-10-14")
        for target in ["D-01", "D-02", "D-03", "D-04", "FAC-SN"]:
            with self.subTest(target=target):
                a, b = investigate(original, target), investigate(decoded, target)
                self.assertEqual(a["summary"], b["summary"])
                self.assertEqual(a["alternatives"], b["alternatives"])

    def test_nine_typed_tools(self):
        self.assertEqual(len(self.tools), 9)
        self.assertTrue(all(t.args_schema for t in self.tools))

    def test_ten_scenario_evaluations(self):
        result = evaluate_graph(self.service.data)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["cases"]), 10)

    def test_tools_preserve_vendor_scope(self):
        report = self.by_name["trace_sourcing_exposure"].invoke({"target": "FAC-AE"})
        self.assertEqual(len(report["summary"]["sku"]), 9)
        self.assertEqual({f["vendor"] for f in report["findings"] if f["sku"] == "A01"}, {"V-NA"})

    def test_alternatives_reject_unrelated_target(self):
        bad = self.by_name["find_sourcing_alternatives"].invoke({"sourcing_ids": ["SA-001"], "target": "DC-E"})
        self.assertEqual(bad["status"], "invalid_scope")
        good = self.by_name["find_sourcing_alternatives"].invoke({"sourcing_ids": ["SA-001"], "target": "FAC-AE"})
        self.assertEqual(good["alternatives"][0]["record"], "SA-002")
        supplier = self.by_name["find_sourcing_alternatives"].invoke({"sourcing_ids": ["SA-001"], "target": "SUP-AP"})
        self.assertEqual(supplier["alternatives"], [])

    def test_missing_evidence_and_date_filters(self):
        result = self.by_name["trace_sourcing_exposure"].invoke({"target": "D-04"})
        self.assertNotIn("B04", result["summary"]["sku"])
        self.assertTrue(any(f["status"] == "unverified_dependency" for f in result["findings"]))
        result = self.by_name["get_disruption_details"].invoke({"disruption_id": "D-01", "on": "2026-11-01"})
        self.assertFalse(result["in_window"])

    def test_unknown_ambiguous_and_disabled_analytics(self):
        self.assertEqual(self.by_name["resolve_entity_tool"].invoke({"name_or_id": "Apex"})["status"], "clarification_required")
        self.assertEqual(self.by_name["resolve_entity_tool"].invoke({"name_or_id": "xyz"})["status"], "not_found")
        self.assertEqual(self.by_name["analyze_supply_communities"].invoke({})["status"], "unavailable")

    def test_workflow_runs_tools_and_cites_evidence(self):
        answer = Answer(status="answered", summary="Apex East exposure checked.",
                        claims=[Claim(text="Basic Tee is potentially exposed.", entity_ids=["A01"], evidence_ids=["E-SA-001"])],
                        limitations=[], next_checks=[], clarification_question="")
        model = ScriptedModel([response("trace_sourcing_exposure", {"target": "FAC-AE"}), AIMessage(content="Done")], answer)
        graph = build_agent(model, self.tools, self.settings)
        result = graph.invoke(turn_input("What depends on Apex East?"))
        self.assertEqual(result["tool_calls_used"], 1)
        self.assertEqual(result["answer"]["status"], "answered")
        self.assertEqual(result["validation_errors"], [])

    def test_fabricated_evidence_is_rejected(self):
        answer = Answer(status="answered", summary="Unsupported.",
                        claims=[Claim(text="Claim", entity_ids=["FAKE"], evidence_ids=["E-NOT-REAL"])],
                        limitations=[], next_checks=[], clarification_question="")
        self.assertTrue(validate_answer(answer, []))

    def test_clarification_survives_checkpoint_and_budget_resets(self):
        answer = Answer(status="clarification_required", summary="Multiple matches.", claims=[], limitations=[],
                        next_checks=[], clarification_question="Which Apex entity?")
        model = ScriptedModel([response("resolve_entity_tool", {"name_or_id": "Apex"}), AIMessage(content="Which?"),
                               response("resolve_entity_tool", {"name_or_id": "FAC-AE"}), AIMessage(content="Resolved")], answer)
        graph = build_agent(model, self.tools, self.settings, InMemorySaver())
        config = {"configurable": {"thread_id": "test"}}
        first = graph.invoke(turn_input("Apex?"), config)
        second = graph.invoke(turn_input("Apex East"), config)
        self.assertEqual(first["answer"]["status"], "clarification_required")
        self.assertEqual(second["tool_calls_used"], 1)
        self.assertEqual(len(second["tool_results"]), 1)
        self.assertGreater(len(second["messages"]), len(first["messages"]))

    def test_budget_and_unknown_tool_are_bounded(self):
        settings = Settings(_env_file=None, agent_max_tool_calls=1)
        answer = Answer(status="insufficient_evidence", summary="Unavailable.", claims=[], limitations=[], next_checks=[], clarification_question="")
        model = ScriptedModel([response("unknown", {})], answer)
        result = build_agent(model, self.tools, settings).invoke(turn_input("Test"))
        self.assertEqual(result["tool_calls_used"], 1)
        self.assertEqual(result["tool_results"][0]["result"]["status"], "unknown_tool")
        self.assertTrue(any("limit" in item for item in result["answer"]["limitations"]))

    def test_tool_errors_do_not_expose_exception_secrets(self):
        self.service.report = Mock(side_effect=RuntimeError("secret-password"))
        answer = Answer(status="insufficient_evidence", summary="Unavailable.", claims=[], limitations=[], next_checks=[], clarification_question="")
        model = ScriptedModel([response("trace_sourcing_exposure", {"target": "FAC-AE"}), AIMessage(content="Failed")], answer)
        result = build_agent(model, self.tools, self.settings).invoke(turn_input("Test"))
        self.assertNotIn("secret-password", json.dumps(result["tool_results"]))


if __name__ == "__main__":
    unittest.main()
