"""Run: uv run python -m supply_chain.agent [--question '...']."""
import argparse
import json
import sys
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver

from .config import ROOT, Settings, create_model
from .repository import FixtureRepository, Neo4jRepository
from .tools import InvestigationService, build_tools
from .workflow import build_agent, render_answer, turn_input
from .errors import classify_api_error


def main():
    parser = argparse.ArgumentParser(description="Supply chain Graph RAG agent (LangChain + LangGraph)")
    parser.add_argument("--question", help="Ask one question instead of opening interactive chat")
    parser.add_argument("--thread", help="Resume a conversation ID; defaults to a new conversation")
    parser.add_argument("--fixture", action="store_true", help="Use local graph data; model calls still use the configured provider")
    parser.add_argument("--check", action="store_true", help="Check graph access and configuration without calling the LLM")
    parser.add_argument("--evaluate-graph", action="store_true", help="Check the ten known graph outcomes without calling the LLM")
    parser.add_argument("--json", action="store_true", help="Print structured answers")
    parser.add_argument("--output", help="Save last answer and tool results as JSON")
    args = parser.parse_args()
    repository = None
    try:
        settings = Settings()
        settings.configure_tracing()
        repository = FixtureRepository() if args.fixture else Neo4jRepository(settings)
        service = InvestigationService(repository, settings.agent_default_date.isoformat())
        service.refresh()
        if args.evaluate_graph:
            from .evaluation import evaluate_graph
            result = evaluate_graph(service.data)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "passed" else 1
        if args.check:
            print(json.dumps(dict(status="ok", backend="fixture" if args.fixture else "neo4j",
                                  model=settings.llm_model,
                                  model_key_configured=bool(settings.llm_api_key.get_secret_value()),
                                  entities=len(service.data["entities"]), sourcing=len(service.data["sourcing"]),
                                  routes=len(service.data["routes"]), evidence=len(service.data["evidence"])), indent=2))
            return 0
        model = create_model(settings)
        thread = args.thread or uuid4().hex
        state_dir = ROOT / ".agent_state"
        state_dir.mkdir(exist_ok=True)
        with SqliteSaver.from_conn_string(str(state_dir / "checkpoints.sqlite")) as saver:
            graph = build_agent(model, build_tools(service), settings, saver)
            config = {"configurable": {"thread_id": thread}, "recursion_limit": settings.agent_max_tool_calls * 2 + 6,
                      "metadata": {"backend": "fixture" if args.fixture else "neo4j"}}
            if not args.json:
                print(f"Conversation: {thread}\nDemo default date: {settings.agent_default_date}. Type /exit to quit.")
            while True:
                question = args.question or input("\nYou: ").strip()
                if question in {"/exit", "/quit"}:
                    break
                if not question:
                    continue
                # Refresh on every turn, including resumed conversations.
                service.refresh()
                result = graph.invoke(turn_input(question), config=config)
                print(json.dumps(result["answer"], indent=2) if args.json else "\nAgent: " + render_answer(result["answer"]))
                if args.output:
                    from pathlib import Path
                    path = Path(args.output)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"thread_id": thread, "answer": result["answer"],
                                               "tool_calls_used": result["tool_calls_used"],
                                               "tools": result["tool_results"],
                                               "validation_errors": result["validation_errors"]}, indent=2), encoding="utf-8")
                if args.question:
                    break
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nConversation closed.")
        return 0
    except Exception as exc:
        # Settings, connection exceptions, and SDK errors can include sensitive values.
        code = getattr(exc, "code", None)
        category = classify_api_error(exc)["kind"]
        if category == "quota":
            print("OpenAI API quota is unavailable. Check API project billing/credits and spending limits. "
                  "The local graph tools and tests can still run.", file=sys.stderr)
            return 1
        if category == "rate" or code in {"tokens", "requests"}:
            print("OpenAI API rate limit reached. Wait before retrying or check project rate limits.", file=sys.stderr)
            return 1
        if "RateLimit" in type(exc).__name__:
            print("OpenAI returned a rate-limit/quota error before completing the answer. "
                  "Check API project usage, billing/credits, spending and rate limits before retrying. "
                  "Run --evaluate-graph to verify graph retrieval without a model call.", file=sys.stderr)
            return 1
        print(f"Agent failed ({type(exc).__name__}). Check local configuration, service connectivity, "
              "API access/billing, and database graph integrity. No credentials are printed.", file=sys.stderr)
        return 1
    finally:
        if repository:
            repository.close()


if __name__ == "__main__":
    raise SystemExit(main())
