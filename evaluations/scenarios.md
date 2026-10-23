# Known-answer evaluation matrix

Default date: 2026-10-14. These expected outcomes follow from the synthetic scenario design, not a second invocation of the query being tested. Automated assertions are in [test_graph_foundation.py](../tests/test_graph_foundation.py).

| Case | Expected result |
|---|---|
| D-01 / Apex East | Supported SKUs A01, A02, A03, B01, B02, B04, F01, F02, F03 |
| A01 under D-01 | Northstar only; Boston, Chicago, Dallas routes; Everyday cotton is unaffected |
| D-01 category reach | Apparel, Footwear, Bags |
| D-02 / Apex supplier | All 12 SKUs; includes Apex West dependencies |
| D-02 alternatives | No unaffected sourcing backups: Apex West belongs to the same disrupted supplier |
| D-03 / East DC | Boston and NYC only; SKUs A01, A02, A03, B01, B02, B04, F01, F03 |
| D-03 backups | Six route-specific backups through Central: A01, F01, B01 for both stores |
| D-04 / zipper | Supported A03, A04, B01, B03, F02; B04 remains unverified |
| D-04 alternatives | None; a component-wide hold is not solved by changing its facility |
| Summit North | F01/TrailWorks and F03/UrbanCarry; Everyday insoles use Flex |
| Summit North fallback | UrbanCarry has approved Flex sourcing; TrailWorks approval is pending |
| Historical FAC-AE on 2025-06-01 | A01/Everyday sourcing exists; distribution coverage unknown |
| Expired Everyday arrangement today | Does not create current Apex East exposure |
| D-01 on 2026-11-01 | Outside notice window |
| Validity boundaries | Start included, end excluded |
| Unknown entity | not_found |
| Ambiguous Apex name | clarification_required with candidates |
| SKU as outage target | unsupported_target |
| Invalid date | Explicit error |
| Missing source | Warning, unverified finding, no unsupported summary claim |
| Broken references / duplicate IDs | Validation errors |
| Re-export | Identical output; every edge endpoint exists |

Live database parity remains a follow-up after import: compare query rows against offline JSON findings, including sourcing ID, route ID, vendor, SKU, store, and evidence status. Import replay should preserve node and relationship counts. No live database results are claimed by the offline suite.
