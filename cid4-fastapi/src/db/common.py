from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from sqlalchemy.ext.asyncio import AsyncSession


class AbstractDbModel(DeclarativeBase, MappedAsDataclass):
    pass


class BaseRepository:
    def __init__(self, session: AsyncSession):
        self._session = session
