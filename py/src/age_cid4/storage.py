from __future__ import annotations

import importlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from age_cid4.graphs import GraphEdge, GraphNode, PropertyGraph

DEFAULT_GRAPH_NAME = "cid4_graph"


@dataclass(frozen=True)
class AgeConfig:
    dsn: str | None
    graph_name: str = DEFAULT_GRAPH_NAME


def load_config_from_env() -> AgeConfig:
    return AgeConfig(
        dsn=os.environ.get("AGE_DSN"),
        graph_name=os.environ.get("AGE_GRAPH_NAME", DEFAULT_GRAPH_NAME),
    )


def import_age_stack() -> dict[str, Any]:
    try:
        return {"psycopg": importlib.import_module("psycopg")}
    except ImportError as exc:
        return {
            "status": "skipped",
            "reason": f"Apache AGE client dependencies are not installed in the current environment: {exc}",
        }


def ingest_graph(graph: PropertyGraph, config: AgeConfig) -> dict[str, Any]:
    if not graph.nodes:
        return {"status": "skipped", "reason": "No graph nodes were generated for Apache AGE ingestion."}

    statements = build_ingestion_statements(graph)
    if not config.dsn:
        return {
            "status": "dry_run",
            "reason": "AGE_DSN is not set; graph statements were prepared but not written to PostgreSQL.",
            "graph_name": config.graph_name,
            "prepared_statement_count": int(len(statements)),
            "node_count": int(len(graph.nodes)),
            "edge_count": int(len(graph.edges)),
            "sample_statements": statements[:5],
        }

    stack = import_age_stack()
    if stack.get("status") == "skipped":
        result = dict(stack)
        result.update(
            {
                "graph_name": config.graph_name,
                "prepared_statement_count": int(len(statements)),
                "node_count": int(len(graph.nodes)),
                "edge_count": int(len(graph.edges)),
                "sample_statements": statements[:5],
            }
        )
        return result

    try:
        with stack["psycopg"].connect(config.dsn, autocommit=True) as connection:
            ensure_age_schema(connection, config)
            for statement in statements:
                execute_cypher(connection, config.graph_name, statement)
    except Exception as exc:  # pragma: no cover - depends on live PostgreSQL + AGE
        return {
            "status": "skipped",
            "reason": f"Apache AGE is not available or not configured on the target PostgreSQL instance: {exc}",
            "graph_name": config.graph_name,
            "prepared_statement_count": int(len(statements)),
            "node_count": int(len(graph.nodes)),
            "edge_count": int(len(graph.edges)),
            "sample_statements": statements[:5],
        }

    return {
        "status": "ok",
        "graph_name": config.graph_name,
        "executed_statement_count": int(len(statements)),
        "node_count": int(len(graph.nodes)),
        "edge_count": int(len(graph.edges)),
    }


def ensure_age_schema(connection: Any, config: AgeConfig) -> None:
    with connection.cursor() as cursor:
        cursor.execute("LOAD 'age'")
        cursor.execute('SET search_path = ag_catalog, "$user", public')
        cursor.execute("SELECT 1 FROM ag_catalog.ag_graph WHERE name = %s", [config.graph_name])
        graph_exists = cursor.fetchone() is not None
        if not graph_exists:
            cursor.execute("SELECT create_graph(%s)", [config.graph_name])


def execute_cypher(connection: Any, graph_name: str, statement: str) -> None:
    sql = f"SELECT * FROM cypher(%s, $$ {statement} $$) AS (result agtype)"
    with connection.cursor() as cursor:
        cursor.execute(sql, [graph_name])


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
