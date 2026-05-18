from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from src.graph.facade import GraphApiFacade
from src.langchain_cid4.facade import LangchainApiFacade


def get_graph_api_facade(request: Request) -> GraphApiFacade:
    engine: AsyncEngine = request.app.state["db_async_engine"]
    return GraphApiFacade(engine)


def get_langchain_api_facade(request: Request) -> LangchainApiFacade:
    engine: AsyncEngine = request.app.state["db_async_engine"]
    return LangchainApiFacade(engine)
