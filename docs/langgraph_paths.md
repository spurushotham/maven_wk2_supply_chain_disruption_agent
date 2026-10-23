# LangGraph Request Paths

This diagram describes the request-specific paths supported by the supply-chain agent. The existing runtime remains bounded and evidence-backed: the model selects only registered typed tools, tool results are recorded in the current turn, and the final answer is validated before it is returned.

## Request routing graph

```mermaid
flowchart TD
    START([User question]) --> LOAD[Load or refresh graph snapshot]
    LOAD --> INIT[Initialize turn state<br/>target, date, messages, evidence ledger]
    INIT --> INTENT[Interpret request intent]

    INTENT --> AMB{Target clear?}
    AMB -- No --> CLARIFY[Ask for clarification<br/>do not choose an entity arbitrarily]
    CLARIFY --> END([End turn])
    AMB -- Yes --> RESOLVE[resolve_entity_tool]

    RESOLVE --> TYPE{What is the user asking about?}

    TYPE -- Supplier, facility,<br/>component, or disruption --> SCOPE1{Request includes alternatives?}
    SCOPE1 -- No --> SOURCE[trace_sourcing_exposure]
    SCOPE1 -- Yes --> SOURCE --> S_ALT[find_sourcing_alternatives]

    TYPE -- Distribution center<br/>or DC disruption --> SCOPE2{Request includes alternatives?}
    SCOPE2 -- No --> DC[trace_dc_exposure]
    SCOPE2 -- Yes --> DC --> R_ALT[find_route_alternatives]

    TYPE -- Exact vendor + SKU<br/>route question --> ROUTE[trace_distribution_exposure]
    ROUTE --> ROUTE_Q{Need source proof?}
    ROUTE_Q -- Yes --> EVIDENCE[get_dependency_evidence]
    ROUTE_Q -- No --> REPORT

    TYPE -- Disruption details,<br/>dates, or scope --> DETAILS[get_disruption_details]
    DETAILS --> REPORT

    TYPE -- Shared facilities,<br/>communities, or concentration --> COMMUNITY[analyze_supply_communities]
    COMMUNITY --> COMMUNITY_NOTE[Mark result as structural insight,<br/>not disruption-impact proof]
    COMMUNITY_NOTE --> REPORT

    SOURCE --> EVIDENCE_GATE{Need exact source excerpts?}
    S_ALT --> EVIDENCE_GATE
    DC --> EVIDENCE_GATE
    R_ALT --> EVIDENCE_GATE
    EVIDENCE_GATE -- Yes --> EVIDENCE[get_dependency_evidence]
    EVIDENCE_GATE -- No --> REPORT
    EVIDENCE --> REPORT

    REPORT[Draft structured answer] --> VALIDATE{Claims cite current-turn<br/>retrieved IDs?}
    VALIDATE -- No --> INSUFFICIENT[Return insufficient_evidence<br/>with limitations and next checks]
    VALIDATE -- Yes --> ANSWER[Return answer with claims,<br/>limitations, evidence, and next checks]

    INSUFFICIENT --> END
    ANSWER --> END

    LIMIT{Tool-call budget remaining?}
    SOURCE -. additional tool call .-> LIMIT
    DC -. additional tool call .-> LIMIT
    ROUTE -. additional tool call .-> LIMIT
    DETAILS -. additional tool call .-> LIMIT
    EVIDENCE -. additional tool call .-> LIMIT
    LIMIT -- No --> REPORT
    LIMIT -- Yes --> INTENT
```

## Path summary

| User request pattern | Primary path | Optional follow-up |
|---|---|---|
| “What is affected by supplier/facility X?” | `resolve_entity_tool` → `trace_sourcing_exposure` | `get_dependency_evidence` |
| “Which backup suppliers can we use?” | `trace_sourcing_exposure` → `find_sourcing_alternatives` | `get_dependency_evidence` |
| “Which stores are affected by DC X?” | `resolve_entity_tool` → `trace_dc_exposure` | `find_route_alternatives` |
| “What routes exist for vendor V and SKU S?” | `resolve_entity_tool` → `trace_distribution_exposure` | `get_dependency_evidence` |
| “What does disruption D cover?” | `resolve_entity_tool` → `get_disruption_details` | `get_dependency_evidence` |
| “Which vendors share production facilities?” | `analyze_supply_communities` | None; result is structural only |
| Ambiguous name or target | `resolve_entity_tool` | Ask the user to select a candidate |
| Unsupported or unverified claim | Final validation | Return `insufficient_evidence` |

## Runtime control loop

The request-specific paths above run inside the existing bounded loop:

```mermaid
flowchart LR
    R[Reason] -->|tool call| T[Execute known typed tool]
    T --> L[Record result and evidence IDs]
    L --> B{Budget remains?}
    B -- Yes --> R
    B -- No --> F[Finalize]
    R -->|no tool call| F
    F --> V[Validate answer]
    V --> O[Return answer]
```

The implementation of this loop is in [`workflow.py`](../supply_chain/agent/workflow.py), and the registered tools are in [`tools.py`](../supply_chain/agent/tools.py).
