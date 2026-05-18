import logging
from asyncio import Lock

from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    AsyncSessionTransaction,
    create_async_engine,
)
from pgvector.psycopg import register_vector_async

from src import constants
from src.config.config import Settings
from src.errors.db_exceptions import DbException

_logger = logging.getLogger(constants.ROOT)


class AsyncDatabaseConnection:
    _lock = Lock()
    _engine: AsyncEngine | None = None

    def __init__(self, settings: Settings):
        self._settings = settings

    async def create_engine(self):
        try:
            async with self._lock:
                if self._engine is None:
                    self._engine = create_async_engine(
                        self._settings.db_url,
                    )

            @event.listens_for(self._engine.sync_engine, "connect")
            def connect(dbapi_connection, connection_record):
                dbapi_connection.run_async(register_vector_async)

            return self._engine
        except Exception as e:
            _logger.exception(e)
            raise DbException("Failed to establish database connection") from e

    async def get_db_version(self):
        connection = await self._engine.connect()
        async with AsyncSession(connection).begin() as session_tx:
            session_tx: AsyncSessionTransaction
            result_cursor = await session_tx.session.execute(text("select version()"))
            version = result_cursor.fetchone()
            _logger.info(version)
        await connection.close()
        return version

    async def close(self):
        if self._engine:
            await self._engine.dispose()


class AppAsyncDatabaseConnection(AsyncDatabaseConnection):
    _instance: AsyncDatabaseConnection | None = None

    @classmethod
    def get_instance(cls, settings: Settings):
        if cls._instance is None:
            cls._instance = cls(settings)
        return cls._instance
