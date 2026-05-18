from sqlalchemy import text

from src.db.common import BaseRepository


_OXYGEN_NEIGHBORS = """
SELECT result.oxygen_aid::integer, result.neighbors::jsonb
FROM ag_catalog.cypher('cid4_graph', $$
    MATCH (o:Atom {element: 'O'})-[\:BOND]-(neighbor:Atom)
	RETURN o.aid AS oxygen_aid, collect({aid: neighbor.aid, element: neighbor.element}) AS neighbors
$$) AS result(oxygen_aid ag_catalog.agtype, neighbors ag_catalog.agtype);
"""

_OXYGEN_TO_NITROGEN_SHORTEST_PATH = """
SELECT result.path_data::jsonb AS path
FROM ag_catalog.cypher('cid4_graph', $$
    MATCH p = (o:Atom {element: 'O'})-[\:BOND*1..10]-(n:Atom {element: 'N'})
    RETURN p, size(relationships(p))
$$) AS result(path_data ag_catalog.agtype, path_len ag_catalog.agtype)
ORDER BY result.path_len::text::integer ASC
LIMIT 1;
"""

_COMPOUND_ASSAY_TARGET_TAXON = """
SELECT 
    result.aid::bigint AS aid,
    result.target::text AS target,
    result.taxonomy_ids::jsonb AS taxonomy_ids
FROM ag_catalog.cypher('cid4_graph', $$
    MATCH (c:Compound {cid: 4})<-[\:ABOUT_COMPOUND]-(a:Assay)-[\:TARGETS]->(t:Target)
    OPTIONAL MATCH (a)-[\:TESTED_IN]->(tax:Taxon)
    RETURN a.aid, t.name, collect(DISTINCT tax.taxonomy_id)
$$) AS result(aid ag_catalog.agtype, target ag_catalog.agtype, taxonomy_ids ag_catalog.agtype);
"""

_COMPOUND_PATHWAY_REACTION_ENZYME = """
SELECT *
FROM ag_catalog.cypher('cid4_graph', $$
    MATCH (c:Compound {cid: 4})-[\:PARTICIPATES_IN]->(p:Pathway)-[\:IN_PATHWAY]->(r:Reaction)
    OPTIONAL MATCH (r)-[\:CATALYZED_BY]->(e:Enzyme)
    RETURN p.pathway_accession, r.reaction, collect(DISTINCT e.enzyme_id)
$$) AS result(pathway_accession ag_catalog.agtype, reaction ag_catalog.agtype, enzymes ag_catalog.agtype);
"""

_COUNT_ORGANISMS_BY_SOURCE = """
SELECT *
FROM ag_catalog.cypher('cid4_graph', $$
    MATCH (c:Compound {cid: 4})-[r]->(o:Organism)
    WHERE type(r) IN ['FOUND_IN', 'ASSOCIATED_WITH']
    OPTIONAL MATCH (o)-[\:FROM_SOURCE]->(s:Source)
    RETURN coalesce(s.name, o.source, 'cid_4.dot') AS source,
           count(DISTINCT o) AS organism_count
    ORDER BY organism_count DESC, source ASC
$$) AS result(source ag_catalog.agtype, organism_count ag_catalog.agtype);
"""


class GraphRepository(BaseRepository):
    async def find_oxygen_neighbors(self):
        return await self._session.execute(text(_OXYGEN_NEIGHBORS))

    async def oxygen_to_nitrogen_shortest_path(self):
        return await self._session.execute(text(_OXYGEN_TO_NITROGEN_SHORTEST_PATH))

    async def compound_assay_target_taxon_relation(self):
        return await self._session.execute(text(_COMPOUND_ASSAY_TARGET_TAXON))

    async def compound_pathway_reaction_enzyme(self):
        return await self._session.execute(text(_COMPOUND_PATHWAY_REACTION_ENZYME))

    async def count_organisms_by_source(self):
        return await self._session.execute(text(_COUNT_ORGANISMS_BY_SOURCE))
