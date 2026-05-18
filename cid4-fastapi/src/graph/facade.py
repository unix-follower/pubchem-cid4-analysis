from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, AsyncSessionTransaction

from src import constants
from .repository import GraphRepository
from .models import OxygenNeighborsResponse, Neighbor


class GraphApiFacade:
    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def get_oxygen_neighbors(self):
        async with (
            self._engine.connect() as connection,
            AsyncSession(connection).begin() as session_tx,
        ):
            session_tx: AsyncSessionTransaction
            repository = GraphRepository(session_tx.session)

            result_cursor = await repository.find_oxygen_neighbors()
            (oxygen_aid, neighbors) = result_cursor.fetchone()

            neighbor_list = [
                Neighbor.model_construct(aid=n["aid"], element=n["element"])
                for n in neighbors
            ]
            result = OxygenNeighborsResponse.model_construct(
                oxygen_aid=oxygen_aid, neighbors=neighbor_list
            )

        return result

    async def get_oxygen_to_nitrogen_shortest_path(self) -> list[dict[str, Any]]:
        async with (
            self._engine.connect() as connection,
            AsyncSession(connection).begin() as session_tx,
        ):
            session_tx: AsyncSessionTransaction
            repository = GraphRepository(session_tx.session)

            result_cursor = await repository.oxygen_to_nitrogen_shortest_path()
            result = result_cursor.fetchone()[constants.ARR_1ST_IDX]

        return result

    async def get_compound_assay_target_taxon_relation(self) -> list[dict[str, Any]]:
        async with (
            self._engine.connect() as connection,
            AsyncSession(connection).begin() as session_tx,
        ):
            session_tx: AsyncSessionTransaction
            repository = GraphRepository(session_tx.session)

            result_cursor = await repository.compound_assay_target_taxon_relation()
            result = result_cursor.fetchone()
            result = result[constants.ARR_1ST_IDX] if result is not None else []

        return result

    async def get_compound_pathway_reaction_enzyme(self) -> list[dict[str, Any]]:
        async with (
            self._engine.connect() as connection,
            AsyncSession(connection).begin() as session_tx,
        ):
            session_tx: AsyncSessionTransaction
            repository = GraphRepository(session_tx.session)

            result_cursor = await repository.compound_pathway_reaction_enzyme()
            result = result_cursor.fetchone()
            result = result[constants.ARR_1ST_IDX] if result is not None else []

        return result

    async def get_count_organisms_by_source(self) -> list[dict[str, Any]]:
        async with (
            self._engine.connect() as connection,
            AsyncSession(connection).begin() as session_tx,
        ):
            session_tx: AsyncSessionTransaction
            repository = GraphRepository(session_tx.session)

            result_cursor = await repository.count_organisms_by_source()
            result = result_cursor.fetchone()
            result = result[constants.ARR_1ST_IDX] if result is not None else []

        return result
