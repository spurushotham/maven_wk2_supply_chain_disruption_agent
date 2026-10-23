// Execute queries individually in Neo4j Browser/Query after importing.
// Change parameters for each investigation. Dates are ISO strings; end is exclusive.
:param target => 'FAC-AE';
:param on => '2026-10-14';

// Entity resolution; names need not be unique.
MATCH (e:Entity)
WHERE e.id = $target OR toLower(e.name) = toLower($target)
RETURN e;

// Supplier/facility/component exposure. Keep sourcing and route vendor paired.
// OPTIONAL MATCH preserves exposed sources with unknown distribution coverage.
MATCH (target:Entity {id: $target})
MATCH (supplier:Supplier)-[:OPERATES]->(facility:ProductionFacility)
MATCH (s:SourcingArrangement)-[:FROM_FACILITY]->(facility)
MATCH (s)-[:FOR_COMPONENT]->(component:Component)
MATCH (s)-[:FOR_SKU]->(sku:SKU)-[:IN_CATEGORY]->(category:Category)
MATCH (s)-[:THROUGH_VENDOR]->(vendor:Vendor)
WHERE (target = supplier OR target = facility OR target = component)
  AND s.role = 'active' AND s.approval = 'approved'
  AND s.valid_from <= $on AND $on < s.valid_to
OPTIONAL MATCH (s)-[:SUPPORTED_BY]->(se:Evidence)
OPTIONAL MATCH (route:DistributionRoute)-[:FOR_SKU]->(sku),
               (route)-[:FROM_VENDOR]->(vendor),
               (route)-[:THROUGH_DC]->(dc:DC), (route)-[:TO_STORE]->(store:Store)
WHERE route.role = 'active' AND route.approval = 'approved'
  AND route.valid_from <= $on AND $on < route.valid_to
OPTIONAL MATCH (route)-[:SUPPORTED_BY]->(re:Evidence)
RETURN supplier.id, facility.id, s.id, component.id, vendor.id, sku.id,
       category.name, route.id, dc.name, store.name,
       se.id AS sourcing_evidence, re.id AS route_evidence,
       CASE WHEN se IS NULL OR (route IS NOT NULL AND re IS NULL)
            THEN 'unverified_dependency' ELSE 'potential_exposure' END AS status
ORDER BY sku.id, vendor.id, store.name;

// DC exposure: set target to DC-E, DC-C, DC-S or DC-W.
MATCH (route:DistributionRoute)-[:THROUGH_DC]->(dc:DC {id: $target}),
      (route)-[:FOR_SKU]->(sku:SKU), (route)-[:FROM_VENDOR]->(vendor:Vendor),
      (route)-[:TO_STORE]->(store:Store)
WHERE route.role = 'active' AND route.approval = 'approved'
  AND route.valid_from <= $on AND $on < route.valid_to
OPTIONAL MATCH (route)-[:SUPPORTED_BY]->(e:Evidence)
RETURN route, dc, sku, vendor, store, e;

// Approved unaffected sourcing alternatives scoped to one exposed arrangement.
:param sourcing_id => 'SA-001';
MATCH (target:Entity {id: $target})
MATCH (original:SourcingArrangement {id: $sourcing_id})-[:FOR_SKU]->(sku:SKU),
      (original)-[:THROUGH_VENDOR]->(vendor:Vendor),
      (original)-[:FOR_COMPONENT]->(component:Component)
MATCH (alt:SourcingArrangement)-[:FOR_SKU]->(sku), (alt)-[:THROUGH_VENDOR]->(vendor),
      (alt)-[:FOR_COMPONENT]->(component), (alt)-[:FROM_FACILITY]->(facility:ProductionFacility),
      (supplier:Supplier)-[:OPERATES]->(facility), (alt)-[:SUPPORTED_BY]->(e:Evidence)
WHERE alt.role = 'backup' AND alt.approval = 'approved'
  AND alt.valid_from <= $on AND $on < alt.valid_to
  AND target <> facility AND target <> supplier AND target <> component
RETURN original.id, alt, facility, supplier, e;

// Approved backup route for the same SKU/vendor/store, excluding the closed DC.
:param route_id => 'DR-001';
MATCH (original:DistributionRoute {id: $route_id})-[:FOR_SKU]->(sku:SKU),
      (original)-[:FROM_VENDOR]->(vendor:Vendor), (original)-[:TO_STORE]->(store:Store)
MATCH (alt:DistributionRoute)-[:FOR_SKU]->(sku), (alt)-[:FROM_VENDOR]->(vendor),
      (alt)-[:TO_STORE]->(store), (alt)-[:THROUGH_DC]->(dc:DC),
      (alt)-[:SUPPORTED_BY]->(e:Evidence)
WHERE alt.role = 'backup' AND alt.approval = 'approved'
  AND alt.valid_from <= $on AND $on < alt.valid_to AND dc.id <> $target
RETURN original.id, alt, dc, e;

// Overview visualization (broad context, not an impact query).
MATCH (a)-[r]->(b)
WHERE NOT a:Evidence AND NOT b:Evidence
RETURN a, r, b LIMIT 500;

// Counts after import.
MATCH (n:Entity) RETURN labels(n) AS labels, count(*) AS nodes ORDER BY labels;
