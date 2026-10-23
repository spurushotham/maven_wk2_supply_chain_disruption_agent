# Data dictionary

All data is fictional. Canonical fixture: [scenario.json](../data/scenario.json). Generator: [graph_fixture.py](../supply_chain/graph_fixture.py).

## Record groups

| Group | Meaning |
|---|---|
| entities | Supplier, ProductionFacility, Vendor, Component, SKU, Category, DC, Store |
| sourcing | A component's approved or pending facility/vendor/SKU sourcing arrangement |
| routes | One vendor/SKU/DC/store distribution arrangement |
| disruptions | Independent hypothetical notices with affected entity and validity dates |
| evidence | Synthetic records supporting business facts |

There are 49 entity records and four disruptions: 53 business nodes. Arrangement, route, and evidence nodes are additional context.

## Common properties

| Property | Semantics |
|---|---|
| id | Globally unique stable identifier across all groups |
| name | Display name; not a unique key |
| label | Neo4j business node type; all exported nodes also have Entity label |
| valid_from | Inclusive ISO date |
| valid_to | Exclusive ISO date; fixed fixture endpoints, not indefinite assumptions |
| role | active or backup |
| approval | approved, pending, or rejected |
| evidence | Supporting record ID; null is a deliberate coverage gap |
| recorded_at | Source recording date; not currently used as a knowledge-time filter |
| synthetic | Explicit marker distinguishing fixture records from operational evidence |

## Scoped relationships

A sourcing arrangement connects to exactly one SKU, vendor, component, and production facility. A distribution route connects to exactly one SKU, vendor, DC, and store. They are first-class nodes because ordinary binary relationships would lose the context of approval and routing.

Master relations describe the synthetic entity register. Production ownership and capabilities are static in this fixture; sourcing and routing are dated. Real ownership/capability history would require additional validity modeling.

`CARRIES` is derived from the fixture's routes and is a discovery aid, not a temporal source of truth. Similarly `SERVES` and `BACKUP_COVERAGE` do not establish a SKU-specific route.

## Source evidence

Readable sources are generated under [data/evidence](../data/evidence/). Record source IDs on scoped nodes and exported edges. `E-MASTER` identifies the canonical entity register; each sourcing/route/disruption record has its own source except intentionally undocumented `SA-067`.

The graph contains no transaction quantities, sales metrics, stock availability, production capacity, or real supplier information. Product component lists are simplified. Polo does not require a buckle; that illustrative planning error is corrected in this fixture.

## Exposure and alternatives

Exposure requires an active, approved, date-valid dependency. A missing source keeps the finding visible as unverified but excludes it from supported summary sets. Duplicate store/SKU summaries are collapsed; separate evidence-bearing sourcing findings remain visible.

Alternative candidates must match SKU + vendor + component (sourcing) or SKU + vendor + store (routing), be backup/approved/date-valid, have source evidence, and avoid the disrupted entity. Alternatives do not imply spare capacity or a complete mitigation plan. Cross-vendor switching and alternate-component substitutions are outside this fixture.
