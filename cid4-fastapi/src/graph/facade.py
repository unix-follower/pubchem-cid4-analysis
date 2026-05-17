from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, AsyncSessionTransaction

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
