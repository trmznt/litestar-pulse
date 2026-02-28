# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


"""Enum key model built with SQLAlchemy 2.0 declarative APIs."""

import json
from collections.abc import Iterable
from typing import Any, TYPE_CHECKING

import yaml
from sqlalchemy import (
    Boolean,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from litestar_pulse.db.models.coremixins import IdentityUserAuditBase

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from typing import TextIO


def _coerce_binary(value: Any) -> bytes | None:
    """Return a binary representation that can be stored in the ``data`` column."""

    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value).encode("utf-8")


class EnumKey(IdentityUserAuditBase):
    """Poor-man enumerated key with optional hierarchical members."""

    __tablename__ = "enumkeys"
    __table_args__ = (
        UniqueConstraint("key", "member_of_id", name="uq_enumkeys_key_member"),
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

    member_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("enumkeys.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    member_of: Mapped["EnumKey | None"] = relationship(
        "EnumKey",
        back_populates="members",
        remote_side="EnumKey.id",
    )
    members: Mapped[list["EnumKey"]] = relationship(
        back_populates="member_of",
        cascade="all, delete-orphan",
        order_by="EnumKey.key",
    )

    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
    )

    def as_dict(self, *, include_members: bool = True) -> dict[str, Any]:
        """Serialize the EK and, optionally, its children."""

        payload: dict[str, Any] = {
            "id": self.id,
            "key": self.key,
            "desc": self.desc,
            "syskey": self.syskey,
            "data": self.data,
            "member_of_id": self.member_of_id,
            "group_id": self.group_id,
            "updated_at": self.updated_at,
        }
        if include_members:
            payload["members"] = [member.as_dict() for member in self.members]
        return payload

    def data_from_json(self) -> Any | None:
        """Return the JSON-decoded ``data`` blob if one is stored."""

        if not self.data:
            return None
        return json.loads(self.data.decode("utf-8"))

    @classmethod
    async def get_by_key(
        cls,
        session: AsyncSession,
        key: str,
        *,
        parent: "EnumKey | None" = None,
        parent_key: str | None = None,
    ) -> "EnumKey | None":
        """Fetch a key optionally scoped by its parent."""

        stmt = select(cls).where(cls.key == key)
        if parent is not None:
            stmt = stmt.where(cls.member_of_id == parent.id)
        elif parent_key is not None:
            parent_stmt = select(cls.id).where(cls.key == parent_key).limit(1)
            stmt = stmt.where(cls.member_of_id == parent_stmt.scalar_subquery())
        return (await session.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def fetch_roots(cls, session: AsyncSession) -> list[EK]:
        """Return all EK instances without parents."""

        stmt = select(cls).where(cls.member_of_id.is_(None)).order_by(cls.key)
        result = await session.execute(stmt)
        return list(result.scalars())

    @classmethod
    async def upsert_from_dict(
        cls,
        session: AsyncSession,
        payload: dict[str, Any],
        *,
        update: bool = False,
        parent: "EnumKey | None" = None,
    ) -> EnumKey:
        """Create or update a key (and recursively its members) from a payload."""

        key = payload["key"]
        instance = await cls.get_by_key(session, key, parent=parent)
        created = instance is None
        if instance is None:
            instance = cls(
                key=key,
                desc=payload.get("desc") or key,
                syskey=bool(payload.get("syskey", False)),
            )
            if parent is not None:
                instance.member_of = parent
        elif parent is not None and instance.member_of_id != parent.id:
            instance.member_of = parent

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
                parent=instance,
            )

        return instance

    @classmethod
    async def upsert_many(
        cls,
        session: AsyncSession,
        payloads: Iterable[dict[str, Any]],
        *,
        update: bool = False,
    ) -> list[EnumKey]:
        """Bulk upsert helper that iterates over payload definitions."""

        results: list[EnumKey] = []
        for payload in payloads:
            results.append(await cls.upsert_from_dict(session, payload, update=update))
        return results

    @classmethod
    async def dump_yaml(
        cls,
        session: AsyncSession,
        stream: TextIO,
        *,
        roots_only: bool = True,
    ) -> None:
        """Write EK definitions as YAML to ``stream``."""

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
        stream: TextIO | str,
        *,
        update: bool = False,
    ) -> list[EnumKey]:
        """Load EK definitions from YAML and upsert them into the database."""

        documents = yaml.safe_load_all(stream)
        created: list[EnumKey] = []
        for payload in documents:
            if not payload:
                continue
            created.append(await cls.upsert_from_dict(session, payload, update=update))
        return created

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<EnumKey key={self.key!r}>"


__all__ = ["EnumKey"]

# EOF
