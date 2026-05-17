from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine

from src.graph.facade import GraphApiFacade


async def get_graph_api_facade(request: Request) -> GraphApiFacade:
    engine: AsyncEngine = request.app.state["db_async_engine"]
    return GraphApiFacade(engine)
