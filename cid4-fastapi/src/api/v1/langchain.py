from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from src.config.dependencies import get_langchain_api_facade
from src.langchain_cid4.facade import LangchainApiFacade

router = APIRouter()


@router.get("/api/v1/lang/ask")
async def ask_literature_question(
    facade: Annotated[LangchainApiFacade, Depends(get_langchain_api_facade)],
):
    body = await facade.ask_literature_question()
    return JSONResponse(content=body)
