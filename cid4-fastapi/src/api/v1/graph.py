from typing import Annotated

from fastapi import APIRouter, Depends
from src.config.dependencies import get_graph_api_facade
from src.graph.facade import GraphApiFacade
from src.graph.models import OxygenNeighborsResponse

router = APIRouter()


@router.get("/api/v1/graph/oxygen-neighbors")
async def graph(
    facade: Annotated[GraphApiFacade, Depends(get_graph_api_facade)],
) -> OxygenNeighborsResponse:
    return await facade.get_oxygen_neighbors()
