from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from src.config.dependencies import get_graph_api_facade
from src.graph.facade import GraphApiFacade
from src.graph.models import OxygenNeighborsResponse

router = APIRouter()


@router.get("/api/v1/graph/oxygen-neighbors")
async def get_oxygen_neighbors(
    facade: Annotated[GraphApiFacade, Depends(get_graph_api_facade)],
) -> OxygenNeighborsResponse:
    return await facade.get_oxygen_neighbors()


@router.get("/api/v1/graph/oxygen-to-nitrogen-shortest-path")
async def get_oxygen_to_nitrogen_shortest_path(
    facade: Annotated[GraphApiFacade, Depends(get_graph_api_facade)],
):
    body = await facade.get_oxygen_to_nitrogen_shortest_path()
    return JSONResponse(content=body)


@router.get("/api/v1/graph/compound-assay-target-taxon-relation")
async def get_compound_assay_target_taxon_relation(
    facade: Annotated[GraphApiFacade, Depends(get_graph_api_facade)],
):
    body = await facade.get_compound_assay_target_taxon_relation()
    return JSONResponse(content=body)


@router.get("/api/v1/graph/compound-pathway-reaction-enzyme")
async def get_compound_pathway_reaction_enzyme(
    facade: Annotated[GraphApiFacade, Depends(get_graph_api_facade)],
):
    body = await facade.get_compound_pathway_reaction_enzyme()
    return JSONResponse(content=body)


@router.get("/api/v1/graph/count-organisms-by-source")
async def get_count_organisms_by_source(
    facade: Annotated[GraphApiFacade, Depends(get_graph_api_facade)],
):
    body = await facade.get_count_organisms_by_source()
    return JSONResponse(content=body)
