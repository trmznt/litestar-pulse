# this file is copied from litestar-fullstack

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Callable, cast

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from litestar.serialization import decode_json, encode_json

from litestar_pulse.db.models.meta import LPAsyncSession


def get_env(var_name: str, default: str) -> str:
    return os.getenv(var_name, default)


def get_bool_env(var_name: str, default: bool) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(var_name: str, default: int) -> int:
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class DBConfig:

    ECHO: bool = field(default_factory=lambda: get_bool_env("DATABASE_ECHO", False))
    """Enable SQLAlchemy engine logs."""
    ECHO_POOL: bool = field(
        default_factory=lambda: get_bool_env("DATABASE_ECHO_POOL", False)
    )
    """Enable SQLAlchemy connection pool logs."""
    POOL_DISABLED: bool = field(
        default_factory=lambda: get_bool_env("DATABASE_POOL_DISABLED", False)
    )
    """Disable SQLAlchemy pool configuration."""
    POOL_MAX_OVERFLOW: int = field(
        default_factory=lambda: get_int_env("DATABASE_MAX_POOL_OVERFLOW", 10)
    )
    """Max overflow for SQLAlchemy connection pool"""
    POOL_SIZE: int = field(default_factory=lambda: get_int_env("DATABASE_POOL_SIZE", 5))
    """Pool size for SQLAlchemy connection pool"""
    POOL_TIMEOUT: int = field(
        default_factory=lambda: get_int_env("DATABASE_POOL_TIMEOUT", 30)
    )
    """Time in seconds for timing connections out of the connection pool."""
    POOL_RECYCLE: int = field(
        default_factory=lambda: get_int_env("DATABASE_POOL_RECYCLE", 300)
    )
    """Amount of time to wait before recycling connections."""
    POOL_PRE_PING: bool = field(
        default_factory=lambda: get_bool_env("DATABASE_PRE_POOL_PING", False)
    )
    """Optionally ping database before fetching a session from the connection pool."""
    URI: str = field(
        default_factory=lambda: get_env("DB_URI", "sqlite+aiosqlite:///db.sqlite3")
    )
    """SQLAlchemy Database URL."""
    MIGRATION_CONFIG: str = field(
        default_factory=lambda: get_env(
            "DATABASE_MIGRATION_CONFIG", f"{BASE_DIR}/db/migrations/alembic.ini"
        )
    )
    """The path to the `alembic.ini` configuration file."""
    MIGRATION_PATH: str = field(
        default_factory=lambda: get_env(
            "DATABASE_MIGRATION_PATH", f"{BASE_DIR}/db/migrations"
        )
    )
    """The path to the `alembic` database migrations."""
    MIGRATION_DDL_VERSION_TABLE: str = field(
        default_factory=lambda: get_env(
            "DATABASE_MIGRATION_DDL_VERSION_TABLE", "ddl_version"
        )
    )
    """The name to use for the `alembic` versions table name."""
    FIXTURE_PATH: str = field(
        default_factory=lambda: get_env(
            "DATABASE_FIXTURE_PATH", f"{BASE_DIR}/db/fixtures"
        )
    )
    """The path to JSON fixture files to load into tables."""

    _engine_instance: AsyncEngine | None = None
    """SQLAlchemy engine instance generated from settings."""

    @property
    def engine(self) -> AsyncEngine:
        return self.get_engine()

    def get_engine(self) -> AsyncEngine:

        if self._engine_instance is not None:
            return self._engine_instance

        if self.URI.startswith("postgresql+asyncpg"):
            engine = create_async_engine(
                url=self.URI,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.ECHO,
                echo_pool=self.ECHO_POOL,
                max_overflow=self.POOL_MAX_OVERFLOW,
                pool_size=self.POOL_SIZE,
                pool_timeout=self.POOL_TIMEOUT,
                pool_recycle=self.POOL_RECYCLE,
                pool_pre_ping=self.POOL_PRE_PING,
                pool_use_lifo=True,  # use lifo to reduce the number of idle connections
                poolclass=NullPool if self.POOL_DISABLED else None,
            )
            """Database session factory.

            See [`async_sessionmaker()`][sqlalchemy.ext.asyncio.async_sessionmaker].
            """

            @event.listens_for(engine.sync_engine, "connect")
            def _sqla_on_connect(
                dbapi_connection: Any, _: Any
            ) -> Any:  # pragma: no cover
                """Using msgspec for serialization of the json column values means that the
                output is binary, not `str` like `json.dumps` would output.
                SQLAlchemy expects that the json serializer returns `str` and calls `.encode()` on the value to
                turn it to bytes before writing to the JSONB column. I'd need to either wrap `serialization.to_json` to
                return a `str` so that SQLAlchemy could then convert it to binary, or do the following, which
                changes the behaviour of the dialect to expect a binary value from the serializer.
                See Also https://github.com/sqlalchemy/sqlalchemy/blob/14bfbadfdf9260a1c40f63b31641b27fe9de12a0/lib/sqlalchemy/dialects/postgresql/asyncpg.py#L934  pylint: disable=line-too-long
                """

                def encoder(bin_value: bytes) -> bytes:
                    return b"\x01" + encode_json(bin_value)

                def decoder(bin_value: bytes) -> Any:
                    # the byte is the \x01 prefix for jsonb used by PostgreSQL.
                    # asyncpg returns it when format='binary'
                    return decode_json(bin_value[1:])

                dbapi_connection.await_(
                    dbapi_connection.driver_connection.set_type_codec(
                        "jsonb",
                        encoder=encoder,
                        decoder=decoder,
                        schema="pg_catalog",
                        format="binary",
                    ),
                )
                dbapi_connection.await_(
                    dbapi_connection.driver_connection.set_type_codec(
                        "json",
                        encoder=encoder,
                        decoder=decoder,
                        schema="pg_catalog",
                        format="binary",
                    ),
                )

        elif self.URI.startswith("sqlite+aiosqlite"):
            engine = create_async_engine(
                url=self.URI,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.ECHO,
                echo_pool=self.ECHO_POOL,
                pool_recycle=self.POOL_RECYCLE,
                pool_pre_ping=self.POOL_PRE_PING,
            )
            """Database session factory.

            See [`async_sessionmaker()`][sqlalchemy.ext.asyncio.async_sessionmaker].
            """

            @event.listens_for(engine.sync_engine, "connect")
            def _sqla_on_connect(
                dbapi_connection: Any, _: Any
            ) -> Any:  # pragma: no cover
                """Override the default begin statement.  The disables the built in begin execution."""
                dbapi_connection.isolation_level = None

            @event.listens_for(engine.sync_engine, "begin")
            def _sqla_on_begin(dbapi_connection: Any) -> Any:  # pragma: no cover
                """Emits a custom begin"""
                dbapi_connection.exec_driver_sql("BEGIN")

        else:
            engine = create_async_engine(
                url=self.URI,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.ECHO,
                echo_pool=self.ECHO_POOL,
                max_overflow=self.POOL_MAX_OVERFLOW,
                pool_size=self.POOL_SIZE,
                pool_timeout=self.POOL_TIMEOUT,
                pool_recycle=self.POOL_RECYCLE,
                pool_pre_ping=self.POOL_PRE_PING,
                pool_use_lifo=True,  # use lifo to reduce the number of idle connections
                poolclass=NullPool if self.POOL_DISABLED else None,
            )
        self._engine_instance = engine
        return self._engine_instance

    @property
    def session_factory(self) -> Callable[[], AsyncEngine]:
        return self.get_session_factory()

    def get_session_factory(self) -> Callable[[], AsyncEngine]:
        return async_sessionmaker(
            self.engine, class_=LPAsyncSession, expire_on_commit=False
        )


# EOF
