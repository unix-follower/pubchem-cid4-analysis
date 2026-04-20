from typing import Any


def build_query_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "oxygen_neighbors",
            "title": "Neighbors of the oxygen atom",
            "cypher": (
                "MATCH (o:Atom {element: 'O'})-[:BOND]-(neighbor:Atom) "
                "RETURN o.aid AS oxygen_aid, collect({aid: neighbor.aid, element: neighbor.element}) AS neighbors"
            ),
        },
        {
            "id": "oxygen_to_nitrogen_shortest_path",
            "title": "Shortest path between oxygen and nitrogen",
            "cypher": ("MATCH p = shortestPath((o:Atom {element: 'O'})-[:BOND*]-(n:Atom {element: 'N'})) RETURN p"),
        },
        {
            "id": "compound_assay_target_taxon",
            "title": "Compound to assay to target to taxon",
            "cypher": (
                "MATCH (c:Compound {cid: 4})<-[:ABOUT_COMPOUND]-(a:Assay)-[:TARGETS]->(t:Target) "
                "OPTIONAL MATCH (a)-[:TESTED_IN]->(tax:Taxon) "
                "RETURN a.aid AS aid, t.name AS target, collect(DISTINCT tax.taxonomy_id) AS taxonomy_ids"
            ),
        },
        {
            "id": "compound_pathway_reaction_enzyme",
            "title": "Compound to pathway to reaction to enzyme",
            "cypher": (
                "MATCH (c:Compound {cid: 4})-[:PARTICIPATES_IN]->(p:Pathway)-[:IN_PATHWAY]->(r:Reaction) "
                "OPTIONAL MATCH (r)-[:CATALYZED_BY]->(e:Enzyme) "
                "RETURN p.pathway_accession AS pathway_accession, r.reaction AS reaction, "
                "collect(DISTINCT e.enzyme_id) AS enzymes"
            ),
        },
        {
            "id": "organism_counts_by_source",
            "title": "Count organisms by source",
            "cypher": (
                "MATCH (c:Compound {cid: 4})-[:FOUND_IN|ASSOCIATED_WITH]->(o:Organism) "
                "OPTIONAL MATCH (o)-[:FROM_SOURCE]->(s:Source) "
                "RETURN coalesce(s.name, o.source, 'cid_4.dot') AS source, count(DISTINCT o) AS organism_count "
                "ORDER BY organism_count DESC, source ASC"
            ),
        },
    ]
