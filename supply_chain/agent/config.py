"""Local configuration. Never serialize Settings into traces or reports."""
from datetime import date
import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8",
                                     extra="ignore", hide_input_in_errors=True)
    neo4j_uri: str = ""
    neo4j_username: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"
    llm_provider: str = "openai"
    llm_model: str = "gpt-5-mini"
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_api_key: SecretStr = SecretStr("")
    ollama_num_ctx: int = Field(default=32768, ge=4096)
    ollama_timeout_seconds: int = Field(default=300, ge=1)
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "supply-chain-impact-agent"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    agent_default_date: date = date(2026, 10, 14)
    agent_max_tool_calls: int = Field(default=12, ge=1, le=40)
    neo4j_query_timeout_seconds: int = Field(default=30, ge=1, le=300)
    community_analytics_enabled: bool = False
    community_session_ttl_minutes: int = Field(default=10, ge=1, le=60)

    def require_database(self):
        if not self.neo4j_uri or not self.neo4j_password.get_secret_value():
            raise ValueError("Fill NEO4J_URI and NEO4J_PASSWORD in .env before using the live database.")

    def configure_tracing(self):
        os.environ["LANGSMITH_TRACING"] = str(self.langsmith_tracing).lower()
        if self.langsmith_tracing:
            if not self.langsmith_api_key.get_secret_value():
                raise ValueError("LANGSMITH_API_KEY is required when tracing is enabled.")
            os.environ["LANGSMITH_API_KEY"] = self.langsmith_api_key.get_secret_value()
            os.environ["LANGSMITH_PROJECT"] = self.langsmith_project
            os.environ["LANGSMITH_ENDPOINT"] = self.langsmith_endpoint


def create_model(settings):
    if settings.llm_provider.casefold() == "ollama_cloud":
        from langchain_ollama import ChatOllama
        if not settings.ollama_api_key.get_secret_value():
            raise ValueError("Fill OLLAMA_API_KEY in .env before using Ollama Cloud.")
        return ChatOllama(model=settings.llm_model, base_url="https://ollama.com",
                          temperature=0,
                          client_kwargs={"timeout": settings.ollama_timeout_seconds,
                                         "headers": {"Authorization": "Bearer " + settings.ollama_api_key.get_secret_value()}})
    if settings.llm_provider.casefold() == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url,
                          temperature=0, num_ctx=settings.ollama_num_ctx,
                          num_predict=5000, reasoning=False,
                          client_kwargs={"timeout": settings.ollama_timeout_seconds})
    from langchain_openai import ChatOpenAI
    if settings.llm_provider.casefold() != "openai":
        raise ValueError("Choose LLM_PROVIDER=openai, ollama, or ollama_cloud.")
    if not settings.llm_api_key.get_secret_value():
        raise ValueError("Fill LLM_API_KEY in .env before running the agent.")
    options = dict(model=settings.llm_model, api_key=settings.llm_api_key,
                   timeout=90, max_retries=1, max_completion_tokens=5000)
    if settings.llm_base_url:
        options["base_url"] = settings.llm_base_url
    if settings.llm_model.startswith("gpt-5"):
        options["reasoning_effort"] = "low"
    return ChatOpenAI(**options)
