# CSV import mapping

Upload the CSV files in this folder using Neo4j Import. CSV upload alone does not define the graph: map nodes and relationships as below.

## Nodes

Create one model node per row. Select its CSV, set the label shown, and select `id` as the unique node ID. Map the other columns as properties. Add the `Entity` label as well if supported; otherwise run the supplied post-import script.

Keep IDs, validity dates, recorded dates, and evidence references as **String**. Set `synthetic` to **Boolean**. The supplied queries compare ISO date strings. Empty evidence cells represent missing values.

| File | Node label | Rows |
|---|---|---:|
| [nodes_Category.csv](nodes_Category.csv) | Category | 3 |
| [nodes_Component.csv](nodes_Component.csv) | Component | 8 |
| [nodes_DC.csv](nodes_DC.csv) | DC | 4 |
| [nodes_Disruption.csv](nodes_Disruption.csv) | Disruption | 4 |
| [nodes_DistributionRoute.csv](nodes_DistributionRoute.csv) | DistributionRoute | 86 |
| [nodes_Evidence.csv](nodes_Evidence.csv) | Evidence | 160 |
| [nodes_ProductionFacility.csv](nodes_ProductionFacility.csv) | ProductionFacility | 6 |
| [nodes_SKU.csv](nodes_SKU.csv) | SKU | 12 |
| [nodes_SourcingArrangement.csv](nodes_SourcingArrangement.csv) | SourcingArrangement | 70 |
| [nodes_Store.csv](nodes_Store.csv) | Store | 8 |
| [nodes_Supplier.csv](nodes_Supplier.csv) | Supplier | 4 |
| [nodes_Vendor.csv](nodes_Vendor.csv) | Vendor | 4 |

## Relationships

Draw each relationship from its start label to its end label. Set its type exactly as shown, select the CSV, map `start_id` to the start node's `id` and `end_id` to the end node's `id`, and map `evidence` as a String property. Endpoint IDs are mappings, not relationship properties.

| File | Start label | Type | End label | Rows |
|---|---|---|---|---:|
| [rels_Category_SUPPORTED_BY_Evidence.csv](rels_Category_SUPPORTED_BY_Evidence.csv) | Category | SUPPORTED_BY | Evidence | 3 |
| [rels_Component_SUPPORTED_BY_Evidence.csv](rels_Component_SUPPORTED_BY_Evidence.csv) | Component | SUPPORTED_BY | Evidence | 8 |
| [rels_DC_BACKUP_COVERAGE_Store.csv](rels_DC_BACKUP_COVERAGE_Store.csv) | DC | BACKUP_COVERAGE | Store | 8 |
| [rels_DC_SERVES_Store.csv](rels_DC_SERVES_Store.csv) | DC | SERVES | Store | 8 |
| [rels_DC_SUPPORTED_BY_Evidence.csv](rels_DC_SUPPORTED_BY_Evidence.csv) | DC | SUPPORTED_BY | Evidence | 4 |
| [rels_Disruption_AFFECTS_Component.csv](rels_Disruption_AFFECTS_Component.csv) | Disruption | AFFECTS | Component | 1 |
| [rels_Disruption_AFFECTS_DC.csv](rels_Disruption_AFFECTS_DC.csv) | Disruption | AFFECTS | DC | 1 |
| [rels_Disruption_AFFECTS_ProductionFacility.csv](rels_Disruption_AFFECTS_ProductionFacility.csv) | Disruption | AFFECTS | ProductionFacility | 1 |
| [rels_Disruption_AFFECTS_Supplier.csv](rels_Disruption_AFFECTS_Supplier.csv) | Disruption | AFFECTS | Supplier | 1 |
| [rels_Disruption_SUPPORTED_BY_Evidence.csv](rels_Disruption_SUPPORTED_BY_Evidence.csv) | Disruption | SUPPORTED_BY | Evidence | 4 |
| [rels_DistributionRoute_FOR_SKU_SKU.csv](rels_DistributionRoute_FOR_SKU_SKU.csv) | DistributionRoute | FOR_SKU | SKU | 86 |
| [rels_DistributionRoute_FROM_VENDOR_Vendor.csv](rels_DistributionRoute_FROM_VENDOR_Vendor.csv) | DistributionRoute | FROM_VENDOR | Vendor | 86 |
| [rels_DistributionRoute_SUPPORTED_BY_Evidence.csv](rels_DistributionRoute_SUPPORTED_BY_Evidence.csv) | DistributionRoute | SUPPORTED_BY | Evidence | 86 |
| [rels_DistributionRoute_THROUGH_DC_DC.csv](rels_DistributionRoute_THROUGH_DC_DC.csv) | DistributionRoute | THROUGH_DC | DC | 86 |
| [rels_DistributionRoute_TO_STORE_Store.csv](rels_DistributionRoute_TO_STORE_Store.csv) | DistributionRoute | TO_STORE | Store | 86 |
| [rels_ProductionFacility_PRODUCES_Component.csv](rels_ProductionFacility_PRODUCES_Component.csv) | ProductionFacility | PRODUCES | Component | 12 |
| [rels_ProductionFacility_SUPPORTED_BY_Evidence.csv](rels_ProductionFacility_SUPPORTED_BY_Evidence.csv) | ProductionFacility | SUPPORTED_BY | Evidence | 6 |
| [rels_SKU_IN_CATEGORY_Category.csv](rels_SKU_IN_CATEGORY_Category.csv) | SKU | IN_CATEGORY | Category | 12 |
| [rels_SKU_REQUIRES_COMPONENT_Component.csv](rels_SKU_REQUIRES_COMPONENT_Component.csv) | SKU | REQUIRES_COMPONENT | Component | 38 |
| [rels_SKU_SUPPORTED_BY_Evidence.csv](rels_SKU_SUPPORTED_BY_Evidence.csv) | SKU | SUPPORTED_BY | Evidence | 12 |
| [rels_SourcingArrangement_FOR_COMPONENT_Component.csv](rels_SourcingArrangement_FOR_COMPONENT_Component.csv) | SourcingArrangement | FOR_COMPONENT | Component | 70 |
| [rels_SourcingArrangement_FOR_SKU_SKU.csv](rels_SourcingArrangement_FOR_SKU_SKU.csv) | SourcingArrangement | FOR_SKU | SKU | 70 |
| [rels_SourcingArrangement_FROM_FACILITY_ProductionFacility.csv](rels_SourcingArrangement_FROM_FACILITY_ProductionFacility.csv) | SourcingArrangement | FROM_FACILITY | ProductionFacility | 70 |
| [rels_SourcingArrangement_SUPPORTED_BY_Evidence.csv](rels_SourcingArrangement_SUPPORTED_BY_Evidence.csv) | SourcingArrangement | SUPPORTED_BY | Evidence | 69 |
| [rels_SourcingArrangement_THROUGH_VENDOR_Vendor.csv](rels_SourcingArrangement_THROUGH_VENDOR_Vendor.csv) | SourcingArrangement | THROUGH_VENDOR | Vendor | 70 |
| [rels_Store_CARRIES_SKU.csv](rels_Store_CARRIES_SKU.csv) | Store | CARRIES | SKU | 60 |
| [rels_Store_SUPPORTED_BY_Evidence.csv](rels_Store_SUPPORTED_BY_Evidence.csv) | Store | SUPPORTED_BY | Evidence | 8 |
| [rels_Supplier_OPERATES_ProductionFacility.csv](rels_Supplier_OPERATES_ProductionFacility.csv) | Supplier | OPERATES | ProductionFacility | 6 |
| [rels_Supplier_SUPPORTED_BY_Evidence.csv](rels_Supplier_SUPPORTED_BY_Evidence.csv) | Supplier | SUPPORTED_BY | Evidence | 4 |
| [rels_Vendor_PROVIDES_SKU.csv](rels_Vendor_PROVIDES_SKU.csv) | Vendor | PROVIDES | SKU | 20 |
| [rels_Vendor_SUPPORTED_BY_Evidence.csv](rels_Vendor_SUPPORTED_BY_Evidence.csv) | Vendor | SUPPORTED_BY | Evidence | 4 |

## Finish

Run the import, then execute [post-import.cypher](post-import.cypher) in the Query workspace. It adds the shared Entity label used by our queries and its ID constraint. It is scoped to this fixture's IDs and business labels.

On an empty database, expect **369 nodes and 1000 relationships**. Run [the investigation queries](../queries.cypher) individually afterward.

Use a fresh demo database or reuse exactly the same ID mappings; do not import the Cypher and CSV versions independently with different mappings.

This is a manual mapping route. For fewer setup steps, [import.cypher](../import.cypher) creates the complete graph through cypher-shell without visual mapping.

Reference: [Neo4j mapping documentation](https://neo4j.com/docs/data-importer/current/mapping/).
