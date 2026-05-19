from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from src.config.dependencies import get_nlp_api_facade
from src.langchain_cid4.facade import NLPApiFacade
from src.api.v1.models import NLPRequest

router = APIRouter()


@router.post("/api/v1/nlp/ask")
async def ask_question(
    nlp_request: NLPRequest,
    facade: Annotated[NLPApiFacade, Depends(get_nlp_api_facade)],
):
    body = await facade.ask_question(nlp_request)
    return JSONResponse(content=body)


@router.post("/api/v1/nlp/execute-graph")
async def execute_graph(
    nlp_request: NLPRequest,
    facade: Annotated[NLPApiFacade, Depends(get_nlp_api_facade)],
):
    body = await facade.execute_graph(nlp_request)
    return JSONResponse(content=body)
