import json
import logging as log
import os
import re
from typing import Any

import psycopg

from .graphs import GraphEdge, GraphNode, PropertyGraph


def ingest_graph(graph: PropertyGraph) -> dict[str, Any]:
    dsn = os.environ.get("AGE_DSN")
    if not dsn:
        raise RuntimeError("AGE_DSN env variable is not set")

    statements = build_ingestion_statements(graph)

    with psycopg.connect(dsn, autocommit=True) as connection:
        set_search_path(connection)
        for statement in statements:
            execute_cypher(connection, statement)

    return {
        "executed_statement_count": int(len(statements)),
        "node_count": int(len(graph.nodes)),
        "edge_count": int(len(graph.edges)),
    }


def set_search_path(connection: Any) -> None:
    with connection.cursor() as cursor:
        sql = 'SET search_path = ag_catalog, "$user", public'
        log.debug(f"Execute SQL: {sql}")
        cursor.execute(sql)


def execute_cypher(connection: Any, statement: str) -> None:
    sql = f"SELECT * FROM cypher('cid4_graph', $$ {statement} $$) AS (result agtype)"
    log.debug(f"Execute SQL: {sql}")
    with connection.cursor() as cursor:
        cursor.execute(sql)


def build_ingestion_statements(graph: PropertyGraph) -> list[str]:
    statements = [build_node_merge_cypher(node) for node in graph.nodes.values()]
    statements.extend(build_edge_merge_cypher(edge) for edge in graph.edges)
    return statements


def build_node_merge_cypher(node: GraphNode) -> str:
    properties = {"graph_id": node.graph_id, **node.properties}
    return (
        f"MERGE (n:{sanitize_label(node.label)} {{graph_id: {cypher_value(node.graph_id)}}}) "
        f"SET n += {cypher_map(properties)}"
    )


def build_edge_merge_cypher(edge: GraphEdge) -> str:
    return (
        f"MATCH (a:{sanitize_label(edge.source_label)} {{graph_id: {cypher_value(edge.source_id)}}}), "
        f"(b:{sanitize_label(edge.target_label)} {{graph_id: {cypher_value(edge.target_id)}}}) "
        f"MERGE (a)-[r:{sanitize_label(edge.label)}]->(b) "
        f"SET r += {cypher_map(edge.properties)}"
    )


def cypher_map(properties: dict[str, Any]) -> str:
    rendered = []
    for key, value in properties.items():
        rendered.append(f"{sanitize_property_key(key)}: {cypher_value(value)}")
    return "{" + ", ".join(rendered) + "}"


def cypher_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(cypher_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return cypher_map(value)
    return json.dumps(str(value))


def sanitize_label(value: str) -> str:
    cleaned = re.sub(r"\W", "_", value)
    if not cleaned:
        return "Unknown"
    if cleaned[0].isdigit():
        cleaned = f"L_{cleaned}"
    return cleaned


def sanitize_property_key(value: str) -> str:
    cleaned = re.sub(r"\W", "_", value)
    if not cleaned:
        return "value"
    if cleaned[0].isdigit():
        cleaned = f"p_{cleaned}"
    return cleaned
