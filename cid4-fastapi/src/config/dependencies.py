from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from src.graph.facade import GraphApiFacade
from src.langchain_cid4.facade import NLPApiFacade


def get_graph_api_facade(request: Request) -> GraphApiFacade:
    engine: AsyncEngine = request.app.state["db_async_engine"]
    return GraphApiFacade(engine)


def get_nlp_api_facade(request: Request) -> NLPApiFacade:
    engine: AsyncEngine = request.app.state["db_async_engine"]
    return NLPApiFacade(engine)
