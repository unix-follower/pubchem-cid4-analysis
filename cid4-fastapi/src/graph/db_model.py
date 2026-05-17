from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.common import AbstractDbModel

GRAPH_ID = "graphid"


class AgGraph(AbstractDbModel):
    __tablename__ = "ag_graph"

    graph_id: Mapped[int] = mapped_column(
        BigInteger(),
        name=GRAPH_ID,
        primary_key=True,
        nullable=False,
        autoincrement=False,
    )
    name: Mapped[str] = mapped_column(String(), nullable=False)
    namespace: Mapped[str] = mapped_column(String(), nullable=False)

    def as_dict(self):
        return {
            GRAPH_ID: self.id_,
            "name": self.name,
            "namespace": self.namespace,
        }
