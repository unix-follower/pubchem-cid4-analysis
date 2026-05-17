from src.api.common import CamelCaseDtoModel


class Neighbor(CamelCaseDtoModel):
    aid: int
    element: str


class OxygenNeighborsResponse(CamelCaseDtoModel):
    oxygen_aid: int
    neighbors: list[Neighbor]
