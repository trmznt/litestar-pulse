# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


import asyncio
import json
from dataclasses import dataclass
from collections.abc import Iterable
from typing import Any, TYPE_CHECKING

import yaml
from sqlalchemy import (
    Boolean,
    String,
    UniqueConstraint,
    LargeBinary,
    ForeignKey,
    select,
    DDL,
    event,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from advanced_alchemy.base import IdentityBase

from litestar_pulse.config.app import logger
from litestar_pulse.db.models.coremixins import IdentityUserAuditBase

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from typing import TextIO


def _coerce_binary(value: Any) -> bytes | None:
    """Return a binary blob suitable for the ``data`` column."""

    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value).encode("utf-8")


def _determine_is_category(payload: dict[str, Any], category: "EnumKey | None") -> bool:
    if "is_category" in payload:
        return bool(payload["is_category"])
    if payload.get("members"):
        return True
    return category is None


class EnumKey(IdentityUserAuditBase):
    """Enumerated key/value pairs grouped under categories."""

    __tablename__ = "enumkeys"
    __table_args__ = (
        UniqueConstraint("key", "category_id", name="uq_enumkeys_key_member"),
    )

    key: Mapped[str] = mapped_column(String(128), nullable=False)
    desc: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    syskey: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("enumkeys.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    category: Mapped["EnumKey | None"] = relationship(
        "EnumKey",
        remote_side="EnumKey.id",
        back_populates="members",
        lazy="joined",
    )
    members: Mapped[list["EnumKey"]] = relationship(
        "EnumKey",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="EnumKey.key",
    )

    is_category: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<EnumKey id={self.id} key={self.key!r}>"

    def __str__(self) -> str:
        return self.key or ""

    def as_dict(self, *, include_members: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "key": self.key,
            "desc": self.desc,
            "syskey": self.syskey,
            "data": self.data,
            "category_id": self.category_id,
            "group_id": self.group_id,
            "updated_at": self.updated_at,
            "is_category": self.is_category,
        }
        if include_members:
            payload["members"] = [member.as_dict() for member in self.members]
        return payload

    def data_from_json(self) -> Any | None:
        if not self.data:
            return None
        return json.loads(self.data.decode("utf-8"))

    @classmethod
    async def get_by_key(
        cls,
        session: AsyncSession,
        key: str,
        *,
        category: "EnumKey | None" = None,
        category_key: str | None = None,
    ) -> "EnumKey | None":
        stmt = select(cls).where(cls.key == key)
        if category is not None:
            stmt = stmt.where(cls.category_id == category.id)
        elif category_key is not None:
            parent_stmt = (
                select(cls.id)
                .where(cls.key == category_key, cls.is_category.is_(True))
                .limit(1)
            )
            stmt = stmt.where(cls.category_id == parent_stmt.scalar_subquery())
        return (await session.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def fetch_roots(cls, session: AsyncSession) -> list["EnumKey"]:
        stmt = select(cls).where(cls.category_id.is_(None)).order_by(cls.key)
        result = await session.execute(stmt)
        return list(result.scalars())

    @classmethod
    async def upsert_from_dict(
        cls,
        session: AsyncSession,
        payload: dict[str, Any],
        *,
        update: bool = False,
        category: "EnumKey | None" = None,
    ) -> "EnumKey":
        key = payload["key"]
        instance = await cls.get_by_key(session, key, category=category)
        created = instance is None
        desired_is_category = _determine_is_category(payload, category)
        if instance is None:
            instance = cls(
                key=key,
                desc=payload.get("desc") or key,
                syskey=bool(payload.get("syskey", False)),
                is_category=desired_is_category,
            )
            if category is not None:
                instance.category = category
        else:
            if category is not None and instance.category_id != category.id:
                instance.category = category
            if update:
                instance.is_category = desired_is_category

        if created or update:
            instance.desc = payload.get("desc", instance.desc)
            if "syskey" in payload:
                instance.syskey = bool(payload["syskey"])
            if "data" in payload:
                instance.data = _coerce_binary(payload.get("data"))

        if "group_id" in payload:
            instance.group_id = payload["group_id"]

        session.add(instance)
        await session.flush()

        for member_payload in payload.get("members", []):
            await cls.upsert_from_dict(
                session,
                member_payload,
                update=update,
                category=instance,
            )

        return instance

    @classmethod
    async def upsert_many(
        cls,
        session: AsyncSession,
        payloads: Iterable[dict[str, Any]],
        *,
        update: bool = False,
    ) -> list["EnumKey"]:
        results: list[EnumKey] = []
        for payload in payloads:
            results.append(await cls.upsert_from_dict(session, payload, update=update))
        return results

    @classmethod
    async def dump_yaml(
        cls,
        session: AsyncSession,
        stream: "TextIO",
        *,
        roots_only: bool = True,
    ) -> None:
        if roots_only:
            objects = await cls.fetch_roots(session)
        else:
            result = await session.execute(select(cls).order_by(cls.key))
            objects = list(result.scalars())

        yaml.safe_dump_all(
            (obj.as_dict() for obj in objects),
            stream,
            default_flow_style=False,
            sort_keys=False,
        )

    @classmethod
    async def load_yaml(
        cls,
        session: AsyncSession,
        stream: "TextIO | str",
        *,
        update: bool = False,
    ) -> list["EnumKey"]:
        documents = yaml.safe_load_all(stream)
        created: list[EnumKey] = []
        for payload in documents:
            if not payload:
                continue
            created.append(await cls.upsert_from_dict(session, payload, update=update))
        return created


class EnumKeyVersion(IdentityBase):
    """One-row table that stores the enum registry version."""

    __tablename__ = "enumkey_versions"

    version: Mapped[int] = mapped_column(
        nullable=False,
        server_default="1",
    )


class EnumKeyRegistryError(RuntimeError):
    """Base exception for registry issues."""


class EnumKeyCategoryNotLoaded(EnumKeyRegistryError):
    """Raised when attempting to use a category that has not been cached."""


class EnumKeyValueNotFound(EnumKeyRegistryError):
    """Raised when a requested value cannot be found within the cached category."""


class EnumKeyCategoryMismatch(EnumKeyRegistryError):
    """Raised when a value/key is used with an incompatible category."""


@dataclass(slots=True, frozen=True)
class EnumKeyValue:
    """Lightweight record used by enumkey proxies."""

    id: int
    key: str
    desc: str
    category_id: int


class EnumKeyRegistry:
    """In-memory cache for enum key categories and their members."""

    _category_ids: dict[str, int] = {}
    _values_by_key: dict[str, dict[str, EnumKeyValue]] = {}
    _values_by_id: dict[int, EnumKeyValue] = {}
    _version: int = 0  # | None = None
    _load_lock: asyncio.Lock | None = None

    @classmethod
    def _get_load_lock(cls) -> asyncio.Lock:
        lock = cls._load_lock
        if lock is None:
            lock = asyncio.Lock()
            cls._load_lock = lock
        return lock

    @classmethod
    async def load_category(cls, session: AsyncSession, category_key: str) -> None:
        """Load every enum key and ensure ``category_key`` exists."""

        await cls.load_all(session)
        if category_key not in cls._category_ids:
            raise EnumKeyCategoryNotLoaded(
                f"Category {category_key!r} is not defined in enumkeys"
            )

    @classmethod
    async def load_categories(cls, session: AsyncSession, *category_keys: str) -> None:
        """Load every enum key and verify each requested category."""

        await cls.load_all(session)
        missing = [key for key in category_keys if key not in cls._category_ids]
        if missing:
            raise EnumKeyCategoryNotLoaded(
                f"Categories {missing!r} are not defined in enumkeys"
            )

    @classmethod
    async def load_all(
        cls,
        session: AsyncSession,
        *,
        version: int | None = None,
    ) -> None:
        """Load the entire enum key table into the registry."""

        async with cls._get_load_lock():
            await cls._load_all_internal(session, version=version)

    @classmethod
    async def _load_all_internal(
        cls,
        session: AsyncSession,
        *,
        version: int | None = None,
    ) -> None:
        rows = list((await session.execute(select(EnumKey))).scalars())
        if version is None:
            version = await cls._fetch_version(session)

        cls.clear()

        category_lookup: dict[int, str] = {}
        category_count = 0
        enumkey_count = 0
        for row in rows:
            if row.is_category:
                category_lookup[row.id] = row.key
                cls._category_ids[row.key] = row.id
                cls._values_by_key.setdefault(row.key, {})
                category_count += 1

        for row in rows:
            if row.category_id is None:
                continue
            category_key = category_lookup.get(row.category_id)
            if category_key is None:
                continue
            cls._register_value(
                category_key,
                EnumKeyValue(
                    id=row.id,
                    key=row.key,
                    desc=row.desc,
                    category_id=row.category_id,
                ),
            )
            enumkey_count += 1
        cls._version = version

        logger.info(
            f"Loaded enum key registry: {category_count} categories, {enumkey_count} values (version {cls._version})"
        )

    @classmethod
    def clear(cls) -> None:
        """Reset the registry (primarily useful for tests)."""

        cls._category_ids.clear()
        cls._values_by_key.clear()
        cls._values_by_id.clear()
        cls._version = None

    @classmethod
    def category_id(cls, category_key: str) -> int | None:
        """Return the cached database identifier for ``category_key`` if available."""

        return cls._category_ids.get(category_key)

    @classmethod
    def get(cls, category_key: str, value_key: str) -> EnumKeyValue:
        """Return the cached value for ``value_key`` within ``category_key``."""

        if category_key not in cls._values_by_key:
            raise EnumKeyCategoryNotLoaded(
                f"Category {category_key!r} has not been loaded into the registry"
            )
        try:
            return cls._values_by_key[category_key][value_key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise EnumKeyValueNotFound(
                f"Enum key {value_key!r} is not registered under {category_key!r}"
            ) from exc

    @classmethod
    def get_by_id(cls, category_key: str | None, value_id: int) -> EnumKeyValue:
        """Return a cached value by its identifier ensuring it belongs to the category."""

        if category_key is None:
            # return the key directly
            try:
                return cls._values_by_id[value_id]
            except KeyError as exc:  # pragma: no cover - defensive
                raise EnumKeyValueNotFound(
                    f"Enum key id {value_id} is not registered in the registry"
                ) from exc

        if category_key not in cls._values_by_key:
            raise EnumKeyCategoryNotLoaded(
                f"Category {category_key!r} has not been loaded into the registry"
            )
        category_id = cls._require_category_id(category_key)
        try:
            record = cls._values_by_id[value_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise EnumKeyValueNotFound(
                f"Enum key id {value_id} is not registered under {category_key!r}"
            ) from exc

        if record.category_id != category_id:
            raise EnumKeyCategoryMismatch(
                f"Enum key id {value_id} belongs to category id {record.category_id}, not {category_id}"
            )
        return record

    @classmethod
    def get_all_keys(cls, category_key: str) -> list[str]:
        """Return all cached keys for a given category."""
        if category_key not in cls._values_by_key:
            raise EnumKeyCategoryNotLoaded(
                f"Category {category_key!r} has not been loaded into the registry"
            )
        return list(cls._values_by_key[category_key].keys())

    @classmethod
    def get_all_items(cls, category_key: str) -> list[EnumKeyValue]:
        """Return all cached values for a given category."""
        if category_key not in cls._values_by_key:
            raise EnumKeyCategoryNotLoaded(
                f"Category {category_key!r} has not been loaded into the registry"
            )
        items = cls._values_by_key[category_key].values()
        item_list = [(item.id, item.key) for item in items]
        return sorted(item_list, key=lambda x: x[1])

    @classmethod
    def ensure_category_id(cls, category_key: str, category_id: int) -> None:
        """Record a category identifier if not cached, validating consistency."""

        existing = cls._category_ids.get(category_key)
        if existing is None:
            cls._category_ids[category_key] = category_id
            return
        if existing != category_id:
            raise EnumKeyCategoryMismatch(
                f"Category {category_key!r} has conflicting ids ({existing} vs {category_id})"
            )

    @classmethod
    def _register_value(cls, category_key: str, record: EnumKeyValue) -> None:
        cls._values_by_key.setdefault(category_key, {})[record.key] = record
        cls._values_by_id[record.id] = record

    @classmethod
    def _require_category_id(cls, category_key: str) -> int:
        try:
            return cls._category_ids[category_key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise EnumKeyCategoryNotLoaded(
                f"Category {category_key!r} is missing its cached identifier"
            ) from exc

    @classmethod
    async def ensure_current(cls, session: AsyncSession) -> None:
        """Reload the registry if the version table indicates changes."""

        # if cls._version is None:
        #    async with cls._get_load_lock():
        #        if cls._version is None:
        #            await cls._load_all_internal(session)
        #    return

        version = await cls._fetch_version(session)
        if version != cls._version:
            async with cls._get_load_lock():
                latest_version = await cls._fetch_version(session)
                if latest_version != cls._version:
                    await cls._load_all_internal(session, version=latest_version)

    @classmethod
    async def _fetch_version(cls, session: AsyncSession) -> int:
        stmt = select(EnumKeyVersion.version).limit(1)
        version = (await session.execute(stmt)).scalar_one_or_none()
        return int(version or 0)


class EnumKeyProxy:
    """Descriptor that exposes enum key members through a foreign key column."""

    __registry__: EnumKeyRegistry = EnumKeyRegistry

    def __init__(self, fk_attribute: str, category_key: str):
        self.fk_attribute = fk_attribute
        self.category_key = category_key
        self.cache_attribute = f"_{fk_attribute}_enumkey_cache"
        self.attr_name: str | None = None

    def __set_name__(
        self, owner: type, name: str
    ) -> None:  # pragma: no cover - trivial
        self.attr_name = name

    def __get__(self, instance, owner=None):  # noqa: ANN001
        if instance is None:
            return self

        fk_value = getattr(instance, self.fk_attribute)
        if fk_value is None:
            instance.__dict__.pop(self.cache_attribute, None)
            return None

        cached = instance.__dict__.get(self.cache_attribute)
        if isinstance(cached, EnumKeyValue) and cached.id == fk_value:
            return cached

        record = EnumKeyRegistry.get_by_id(self.category_key, fk_value)
        instance.__dict__[self.cache_attribute] = record
        return record

    def __set__(self, instance, value):  # noqa: ANN001
        if value is None:
            setattr(instance, self.fk_attribute, None)
            instance.__dict__.pop(self.cache_attribute, None)
            return

        record = self._coerce_value(value)
        setattr(instance, self.fk_attribute, record.id)
        instance.__dict__[self.cache_attribute] = record

    def _coerce_value(self, value) -> EnumKeyValue:  # noqa: ANN001
        if isinstance(value, EnumKeyValue):
            record = value
        elif isinstance(value, EnumKey):
            if value.category_id is None:
                raise EnumKeyRegistryError(
                    "EnumKey instance does not belong to a category and cannot be proxied"
                )
            EnumKeyRegistry.ensure_category_id(self.category_key, value.category_id)
            record = EnumKeyValue(
                id=value.id,
                key=value.key,
                desc=value.desc,
                category_id=value.category_id,
            )
            EnumKeyRegistry._register_value(self.category_key, record)
        elif isinstance(value, str):
            record = EnumKeyRegistry.get(self.category_key, value)
        elif isinstance(value, int):
            record = EnumKeyRegistry.get_by_id(self.category_key, value)
        else:  # pragma: no cover - defensive
            raise TypeError(
                f"Unsupported value {value!r} for enum key proxy {self.attr_name or ''}"
            )

        expected_category_id = EnumKeyRegistry._require_category_id(self.category_key)
        if record.category_id != expected_category_id:
            raise EnumKeyCategoryMismatch(
                f"Enum key {record.key!r} does not belong to category {self.category_key!r}"
            )
        return record


_ENUMKEY_TABLE = EnumKey.__table__.name
_ENUMKEY_VERSION_TABLE = EnumKeyVersion.__table__.name

_POSTGRES_FUNCTION_NAME = f"{_ENUMKEY_TABLE}_version_bump_fn"
_POSTGRES_TRIGGER_NAME = f"{_ENUMKEY_TABLE}_version_bump_trg"

_POSTGRES_CREATE_FUNCTION = DDL(
    f"""
    CREATE OR REPLACE FUNCTION {_POSTGRES_FUNCTION_NAME}()
    RETURNS TRIGGER AS $$
    BEGIN
        UPDATE {_ENUMKEY_VERSION_TABLE} SET version = version + 1;
        IF NOT FOUND THEN
            INSERT INTO {_ENUMKEY_VERSION_TABLE} (version) VALUES (1);
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

_POSTGRES_DROP_FUNCTION = DDL(
    f"DROP FUNCTION IF EXISTS {_POSTGRES_FUNCTION_NAME}() CASCADE;"
)

_POSTGRES_CREATE_TRIGGER = DDL(
    f"""
    CREATE TRIGGER {_POSTGRES_TRIGGER_NAME}
        AFTER INSERT OR UPDATE OR DELETE ON {_ENUMKEY_TABLE}
        FOR EACH ROW EXECUTE FUNCTION {_POSTGRES_FUNCTION_NAME}();
    """
)

_POSTGRES_DROP_TRIGGER = DDL(
    f"DROP TRIGGER IF EXISTS {_POSTGRES_TRIGGER_NAME} ON {_ENUMKEY_TABLE};"
)

_SQLITE_TRIGGER_INSERT = DDL(
    f"""
    CREATE TRIGGER IF NOT EXISTS {_ENUMKEY_TABLE}_version_bump_insert
    AFTER INSERT ON {_ENUMKEY_TABLE}
    BEGIN
        UPDATE {_ENUMKEY_VERSION_TABLE} SET version = version + 1;
        INSERT INTO {_ENUMKEY_VERSION_TABLE} (version)
        SELECT 1 WHERE changes() = 0;
    END;
    """
)

_SQLITE_TRIGGER_UPDATE = DDL(
    f"""
    CREATE TRIGGER IF NOT EXISTS {_ENUMKEY_TABLE}_version_bump_update
    AFTER UPDATE ON {_ENUMKEY_TABLE}
    BEGIN
        UPDATE {_ENUMKEY_VERSION_TABLE} SET version = version + 1;
        INSERT INTO {_ENUMKEY_VERSION_TABLE} (version)
        SELECT 1 WHERE changes() = 0;
    END;
    """
)

_SQLITE_TRIGGER_DELETE = DDL(
    f"""
    CREATE TRIGGER IF NOT EXISTS {_ENUMKEY_TABLE}_version_bump_delete
    AFTER DELETE ON {_ENUMKEY_TABLE}
    BEGIN
        UPDATE {_ENUMKEY_VERSION_TABLE} SET version = version + 1;
        INSERT INTO {_ENUMKEY_VERSION_TABLE} (version)
        SELECT 1 WHERE changes() = 0;
    END;
    """
)

_SQLITE_DROP_INSERT = DDL(
    f"DROP TRIGGER IF EXISTS {_ENUMKEY_TABLE}_version_bump_insert;"
)
_SQLITE_DROP_UPDATE = DDL(
    f"DROP TRIGGER IF EXISTS {_ENUMKEY_TABLE}_version_bump_update;"
)
_SQLITE_DROP_DELETE = DDL(
    f"DROP TRIGGER IF EXISTS {_ENUMKEY_TABLE}_version_bump_delete;"
)

event.listen(
    EnumKey.__table__,
    "after_create",
    _POSTGRES_CREATE_FUNCTION.execute_if(dialect="postgresql"),
)
event.listen(
    EnumKey.__table__,
    "after_create",
    _POSTGRES_CREATE_TRIGGER.execute_if(dialect="postgresql"),
)
event.listen(
    EnumKey.__table__,
    "before_drop",
    _POSTGRES_DROP_TRIGGER.execute_if(dialect="postgresql"),
)
event.listen(
    EnumKey.__table__,
    "before_drop",
    _POSTGRES_DROP_FUNCTION.execute_if(dialect="postgresql"),
)

for ddl in (
    _SQLITE_TRIGGER_INSERT,
    _SQLITE_TRIGGER_UPDATE,
    _SQLITE_TRIGGER_DELETE,
):
    event.listen(EnumKey.__table__, "after_create", ddl.execute_if(dialect="sqlite"))

for ddl in (_SQLITE_DROP_INSERT, _SQLITE_DROP_UPDATE, _SQLITE_DROP_DELETE):
    event.listen(EnumKey.__table__, "before_drop", ddl.execute_if(dialect="sqlite"))


def enumkey_proxy(foreign_key_attr: str, category_key: str) -> EnumKeyProxy:
    """Factory helper that mirrors the desired API used by models."""

    return EnumKeyProxy(foreign_key_attr, category_key)


__all__ = [
    "EnumKey",
    "EnumKeyVersion",
    "EnumKeyRegistry",
    "EnumKeyValue",
    "enumkey_proxy",
    "EnumKeyRegistryError",
    "EnumKeyCategoryNotLoaded",
    "EnumKeyValueNotFound",
    "EnumKeyCategoryMismatch",
]
