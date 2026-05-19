from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from src.api.v1.models import NLPRequest
from src.langchain_cid4.workflows import run_question_workflow
from src.langgraph_cid4.workflows import (
    run_assay_literature_workflow,
    run_compound_context_workflow,
    run_pathway_taxonomy_workflow,
    run_router_workflow,
)


class NLPApiFacade:
    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def ask_question(self, nlp_request: NLPRequest) -> dict[str, Any]:
        return await run_question_workflow(
            nlp_request.question,
            domains=nlp_request.domains,
            workflow=nlp_request.workflow,
            engine=self._engine,
        )

    async def execute_graph(self, nlp_request: NLPRequest) -> dict[str, Any]:
        match nlp_request.workflow:
            case "assay-plus-literature":
                return await run_assay_literature_workflow(
                    nlp_request, engine=self._engine
                )
            case "pathway-taxonomy":
                return await run_pathway_taxonomy_workflow(nlp_request)
            case "compound-context-assistant":
                return await run_compound_context_workflow(
                    nlp_request, engine=self._engine
                )
            case "router-graph":
                return await run_router_workflow(nlp_request, engine=self._engine)
