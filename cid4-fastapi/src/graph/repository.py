from sqlalchemy import text

from src.db.common import BaseRepository


_OXYGEN_NEIGHBORS = """
SELECT result.oxygen_aid::integer, result.neighbors::jsonb
FROM ag_catalog.cypher('cid4_graph', $$
    MATCH (o:Atom {element: 'O'})-[\:BOND]-(neighbor:Atom)
	RETURN o.aid AS oxygen_aid, collect({aid: neighbor.aid, element: neighbor.element}) AS neighbors
$$) AS result(oxygen_aid ag_catalog.agtype, neighbors ag_catalog.agtype);
"""


class GraphRepository(BaseRepository):
    async def find_oxygen_neighbors(self):
        return await self._session.execute(text(_OXYGEN_NEIGHBORS))
