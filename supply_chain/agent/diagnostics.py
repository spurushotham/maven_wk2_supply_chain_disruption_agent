"""One minimal model request, no automatic retries; prints only safe diagnostics."""
import json
from .config import Settings, create_model
from .errors import classify_api_error


def main():
    try:
        settings = Settings()
        model = create_model(settings)
        if settings.llm_provider.casefold() in {"ollama", "ollama_cloud"}:
            model.num_predict = 64
        else:
            model.max_retries = 0
            model.max_tokens = 64
        model.invoke("Reply OK.", config={"callbacks": []})
        print(json.dumps({"status": "ok", "message": "Model request succeeded."}))
        return 0
    except Exception as exc:
        result = classify_api_error(exc)
        result["status"] = "failed"
        result["exception"] = type(exc).__name__
        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            result["http_status"] = status
        print(json.dumps(result))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
