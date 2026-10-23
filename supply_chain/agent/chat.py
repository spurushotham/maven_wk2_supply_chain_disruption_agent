"""Session-isolated chat adapter shared by the UI and its tests."""
from .config import Settings, create_model
from .repository import FixtureRepository, Neo4jRepository
from .tools import InvestigationService, build_tools
from .workflow import ReportFormatError, build_agent, turn_input
from .errors import classify_api_error


def user_error(exc):
    """Do not expose raw SDK errors, which can contain credentials or endpoints."""
    if isinstance(exc, ReportFormatError):
        return "The model did not produce a valid report after two formatting attempts. Try a narrower question or a different tool-capable model. No unvalidated answer was displayed."
    kind = type(exc).__name__
    if type(exc).__module__.startswith("ollama"):
        if getattr(exc, "status_code", None) in {401, 403}:
            return "Ollama denied access. Check OLLAMA_API_KEY and your account's access to the configured cloud model."
        if getattr(exc, "status_code", None) == 429:
            return "Ollama reports a usage or rate limit. Check your Ollama account usage and retry when allowance is available."
        if getattr(exc, "status_code", None) == 404:
            return "Ollama could not find the configured model. For local Ollama, run ollama pull with the LLM_MODEL value. For Ollama Cloud, choose a model listed by https://ollama.com/api/tags."
        return "Ollama could not complete the request. Check that the model supports tool calling, is loaded, and fits in available memory."
    category = classify_api_error(exc)["kind"]
    if category == "quota":
        return "OpenAI reports an API billing or quota limit. Check the billing/credits and usage limits for the organization and project that own this API key. Waiting or resending the question will not resolve an exhausted quota."
    if category == "rate":
        return "OpenAI reports a temporary request/token rate limit. Wait briefly and retry; if it persists, check the model's rate limits for your API project."
    if "RateLimit" in kind or getattr(exc, "code", None) == "insufficient_quota":
        return "OpenAI couldn't complete this request because of an API rate or quota limit. Check your API billing and usage limits, then try again."
    if "Authentication" in kind or "AuthError" in kind:
        return "Authentication failed. Check the API key and database credentials in your local configuration."
    if "Connection" in kind or "ConnectError" in kind or "ServiceUnavailable" in kind or "SessionExpired" in kind:
        return "A service could not be reached. Check that Neo4j and your model service are running. For Ollama, start the Ollama app or run ollama serve and verify OLLAMA_BASE_URL."
    if "Timeout" in kind:
        return "The request timed out. Please try a narrower question or retry shortly."
    return "The investigation couldn't finish. Check your local configuration and service access, then try again."


def run_chat_turn(question, history, backend, on, progress=None):
    settings = Settings(agent_default_date=on)
    settings.configure_tracing()
    repository = FixtureRepository() if backend == "Local sample" else Neo4jRepository(settings)
    try:
        service = InvestigationService(repository, settings.agent_default_date.isoformat())
        if progress:
            progress("Reading supply chain records…")
        service.refresh()
        graph = build_agent(create_model(settings), build_tools(service), settings)
        state = turn_input(question)
        # No shared checkpointer or global cache: each browser session owns its history.
        state["messages"] = list(history) + state["messages"]
        result = None
        for state in graph.stream(state, {"recursion_limit": settings.agent_max_tool_calls * 2 + 6}, stream_mode="values"):
            result = state
            if progress:
                progress("Preparing evidence-backed answer…" if state.get("answer") else
                         f"Investigating dependencies · {state.get('tool_calls_used', 0)} checks completed")
        if not result or not result.get("answer"):
            raise RuntimeError("Workflow ended without an answer")
        cited = {id for claim in result["answer"]["claims"] for id in claim["evidence_ids"]}
        sources = [e for e in service.data["evidence"] if e["id"] in cited]
        return {"answer": result["answer"], "messages": result["messages"], "sources": sources,
                "checks": result["tool_calls_used"], "date": settings.agent_default_date.isoformat(),
                "backend": backend}
    finally:
        repository.close()


def check_graph(backend, on):
    settings = Settings(agent_default_date=on)
    repository = FixtureRepository() if backend == "Local sample" else Neo4jRepository(settings)
    try:
        data = repository.snapshot()
        return {"entities": len(data["entities"]), "sourcing": len(data["sourcing"]), "routes": len(data["routes"])}
    finally:
        repository.close()
