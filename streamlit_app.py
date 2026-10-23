"""Launch with: python -m uv run streamlit run streamlit_app.py"""
import json

import streamlit as st

from supply_chain.agent.chat import check_graph, run_chat_turn, user_error
from supply_chain.agent.config import Settings

st.set_page_config(page_title="Supply Chain Investigator", page_icon="🔎", layout="wide")


def reset_chat():
    st.session_state.chat_entries = []
    st.session_state.agent_messages = []
    st.session_state.pop("connection_result", None)


def show_answer(entry, index):
    answer = entry["answer"]
    st.markdown(answer["summary"])
    if answer.get("clarification_question"):
        st.info(answer["clarification_question"])
    for claim in answer["claims"]:
        st.markdown(f"- {claim['text']}")
        if claim["evidence_ids"]:
            st.caption("Sources: " + ", ".join(claim["evidence_ids"]))
    if answer["limitations"]:
        with st.expander("Scope and limitations"):
            for item in answer["limitations"]:
                st.markdown(f"- {item}")
    if answer["next_checks"]:
        st.markdown("**Suggested next checks**")
        for item in answer["next_checks"]:
            st.markdown(f"- {item}")
    if entry["sources"]:
        with st.expander(f"Supporting evidence ({len(entry['sources'])})"):
            for source in entry["sources"]:
                st.markdown(f"**{source['id']} · {source['title']}**")
                st.text(source["text"])
    st.caption(f"As of {entry['date']} · {entry['backend']} · {entry['checks']} investigation checks")
    exported = {k: v for k, v in entry.items() if k not in {"role", "messages"}}
    st.download_button("Download findings", json.dumps(exported, indent=2),
                       file_name=f"supply-chain-findings-{index}.json", mime="application/json", key=f"download_{index}")


if "chat_entries" not in st.session_state:
    reset_chat()

try:
    settings = Settings()
except Exception:
    st.error("Could not load configuration. Check the values in your local .env file.")
    st.stop()

with st.sidebar:
    st.header("Investigation settings")
    backend = st.selectbox("Data source", ["Neo4j", "Local sample"], index=1,
                           key="backend", on_change=reset_chat)
    on = st.date_input("Default investigation date", value=settings.agent_default_date,
                       key="investigation_date", on_change=reset_chat)
    st.caption("The sample scenario is set in October 2026. Changing the date or data source starts a new conversation.")
    st.button("New conversation", on_click=reset_chat, use_container_width=True)
    if st.button("Check graph connection", use_container_width=True):
        try:
            with st.spinner("Checking graph access…"):
                st.session_state.connection_result = {"ok": True, "counts": check_graph(backend, on)}
        except Exception as exc:
            st.session_state.connection_result = {"ok": False, "error": user_error(exc)}
    connection = st.session_state.get("connection_result")
    if connection:
        if connection["ok"]:
            st.success("Graph connection verified")
            counts = connection["counts"]
            st.caption(f"{counts['entities']} entities · {counts['sourcing']} sourcing arrangements · {counts['routes']} routes")
        else:
            st.error(connection["error"])
    st.divider()
    st.caption(f"Provider: {settings.llm_provider} | Model: {settings.llm_model}")
    st.caption("Community analysis: " + ("enabled (Aura usage charges may apply)" if settings.community_analytics_enabled else "disabled"))
    if settings.llm_provider.casefold() == "ollama_cloud":
        st.caption("Answers use Ollama Cloud. Questions and retrieved evidence are sent to Ollama; cloud account usage limits apply. No local Ollama installation is needed.")
    elif settings.llm_provider.casefold() == "ollama":
        st.caption("Answers use your Ollama server. Start Ollama and pull the configured model before chatting. No OpenAI API key is needed.")
    else:
        st.caption("Both data sources use OpenAI to answer questions. Credentials are read on the server from your local configuration.")

st.title("Supply Chain Investigator")
st.write("Explore disruption exposure, approved alternatives, and the evidence behind each finding.")
st.caption("Synthetic supply chain · Potential exposure, not a forecast of stockouts")

missing = []
if settings.llm_provider.casefold() == "ollama_cloud" and not settings.ollama_api_key.get_secret_value():
    missing.append("OLLAMA_API_KEY")
if settings.llm_provider.casefold() == "openai" and not settings.llm_api_key.get_secret_value():
    missing.append("LLM_API_KEY")
if backend == "Neo4j":
    if not settings.neo4j_uri:
        missing.append("NEO4J_URI")
    if not settings.neo4j_password.get_secret_value():
        missing.append("NEO4J_PASSWORD")
if missing:
    st.warning("Add these settings to your local .env before chatting: " + ", ".join(missing))

suggestion = None
if not st.session_state.chat_entries:
    st.markdown("**Start an investigation**")
    examples = ["Apex East shut down. Which SKUs and stores could be affected?",
                "If East DC closes, what approved backup routes exist?",
                "Can Apex West replace Apex East if the entire Apex supplier is unavailable?"]
    for i, column in enumerate(st.columns(3)):
        if column.button(examples[i], key=f"example_{i}", disabled=bool(missing), use_container_width=True):
            suggestion = examples[i]

for i, entry in enumerate(st.session_state.chat_entries):
    with st.chat_message(entry["role"]):
        if entry.get("error"):
            st.error(entry["error"])
        elif entry["role"] == "user":
            st.markdown(entry["content"])
        else:
            show_answer(entry, i)

question = st.chat_input("Ask about a disruption, product, store, or alternative…", disabled=bool(missing)) or suggestion
if question:
    st.session_state.chat_entries.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.status("Starting investigation…", expanded=False) as status:
            try:
                result = run_chat_turn(question, st.session_state.agent_messages, backend, on,
                                       progress=lambda message: status.update(label=message))
                # Commit history only after a complete successful turn. Failed calls don't poison follow-ups.
                st.session_state.agent_messages = result.pop("messages")
                entry = {"role": "assistant", **result}
                st.session_state.chat_entries.append(entry)
                status.update(label="Investigation complete", state="complete")
            except Exception as exc:
                entry = {"role": "assistant", "error": user_error(exc)}
                st.session_state.chat_entries.append(entry)
                status.update(label="Investigation could not finish", state="error")
        if entry.get("error"):
            st.error(entry["error"])
        else:
            show_answer(entry, len(st.session_state.chat_entries) - 1)
