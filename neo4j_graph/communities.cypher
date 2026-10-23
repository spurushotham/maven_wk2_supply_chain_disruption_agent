// Run sections individually in Aura Query; do not run this entire file at once.
// Step 2 starts an Aura Graph Analytics session (subject to your plan's charges).
// No business nodes/relationships or community properties are written.
// Docs: https://neo4j.com/docs/graph-data-science/current/aura-graph-analytics/quickstart/

// 1. Preview eligible vendor/SKU combinations and their distinct facilities.
:param on => '2026-10-14';
MATCH (s:SourcingArrangement)-[:FOR_SKU]->(sku:SKU),
      (s)-[:THROUGH_VENDOR]->(vendor:Vendor),
      (s)-[:FOR_COMPONENT]->(component:Component),
      (s)-[:FROM_FACILITY]->(facility:ProductionFacility)
WHERE s.role = 'active' AND s.approval = 'approved'
  AND s.valid_from <= $on AND $on < s.valid_to
  AND component.id <> 'C-SC'
  AND EXISTS { MATCH (s)-[:SUPPORTED_BY]->(:Evidence) }
RETURN vendor.name AS vendor, sku.id AS sku, sku.name AS product,
       collect(DISTINCT facility.name) AS documentedFacilities
ORDER BY vendor, sku;

// 2. Project the weighted, undirected shared-facility graph.
// Use one existing arrangement as a stable representative of each vendor/SKU pair.
// All eligible arrangements contribute facilities, not just the representative.
// This avoids adding synthetic vendor/SKU nodes to the business database.
// Excluded undocumented dependencies are missing coverage, not proven independence.
MATCH (s:SourcingArrangement)-[:FOR_SKU]->(sku:SKU),
      (s)-[:THROUGH_VENDOR]->(vendor:Vendor),
      (s)-[:FOR_COMPONENT]->(component:Component),
      (s)-[:FROM_FACILITY]->(facility:ProductionFacility)
WHERE s.role = 'active' AND s.approval = 'approved'
  AND s.valid_from <= $on AND $on < s.valid_to
  AND component.id <> 'C-SC'
  AND EXISTS { MATCH (s)-[:SUPPORTED_BY]->(:Evidence) }
WITH vendor, sku, s, facility ORDER BY s.id
WITH vendor, sku, head(collect(s)) AS representative,
     collect(DISTINCT facility.id) AS facilities
WITH collect({node: representative, facilities: facilities}) AS pairs
UNWIND pairs AS source
WITH source, [other IN pairs
  WHERE source.node.id < other.node.id
    AND any(f IN source.facilities WHERE f IN other.facilities)
  | {node: other.node,
     weight: size([f IN source.facilities WHERE f IN other.facilities])}] AS neighbors
// Null targets preserve nodes even when they have no outgoing pair here.
UNWIND CASE WHEN size(neighbors) = 0 THEN [{node: null, weight: 0}] ELSE neighbors END AS target
WITH gds.graph.project(
  'supply-communities-20261014', source.node, target.node,
  {relationshipType: 'SHARES_FACILITY', relationshipProperties: {weight: target.weight}},
  {undirectedRelationshipTypes: ['SHARES_FACILITY'], memory: '2GB', ttl: duration({minutes: 10})}
) AS projected
RETURN projected.graphName AS graphName, projected.nodeCount AS nodeCount,
       projected.relationshipCount AS relationshipCount;

// 3. Run Leiden and resolve representative arrangement nodes back to vendor/SKU.
// Community IDs are arbitrary group identifiers, not risk scores or causal claims.
CALL gds.leiden.stream('supply-communities-20261014', {
  relationshipWeightProperty: 'weight', randomSeed: 42, concurrency: 1
})
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) AS representative, communityId
MATCH (representative)-[:FOR_SKU]->(sku:SKU),
      (representative)-[:THROUGH_VENDOR]->(vendor:Vendor)
RETURN communityId, vendor.name AS vendor, sku.id AS sku, sku.name AS product
ORDER BY communityId, vendor, sku;

// 4. After inspecting/exporting results, release the temporary graph/session.
// This does not delete the stored supply-chain graph.
CALL gds.graph.drop('supply-communities-20261014');

// Before rerunning step 2 with this same name, drop its previous projection.
// The in-memory session may also expire after inactivity; recreate it if needed.
