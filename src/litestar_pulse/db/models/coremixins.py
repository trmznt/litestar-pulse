# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import fastnanoid

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from contextvars import ContextVar
from typing import TYPE_CHECKING, Self, Any, Generic, TypeVar, get_args, Optional, Type
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from functools import cached_property


from uuid_utils.compat import uuid7
from sqlalchemy import String, ForeignKey, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    declarative_mixin,
    declared_attr,
)


from advanced_alchemy.base import IdentityAuditBase
from advanced_alchemy.mixins.sentinel import SentinelMixin
from advanced_alchemy.types import FileObject, FileObjectList, StoredObject

from litestar_pulse.lib import roles as r

if TYPE_CHECKING:
    from .account import User

T = TypeVar("T")

_current_userid: ContextVar[int | None] = ContextVar("_current_userid", default=None)


def set_current_userid(user_id: int | None) -> None:
    """Set the current user ID for audit columns."""
    _current_userid.set(user_id)


def get_current_userid() -> int | None:
    """Return the current user ID, or None if not set (e.g. during seeding)."""
    return _current_userid.get()


@declarative_mixin
class UUIDv7UniqueKey(SentinelMixin):

    uuid: Mapped[UUID] = mapped_column(default=uuid7, unique=True, sort_order=-100)
    """UUID unique key column."""

    def __init__(self, **kwargs: any) -> None:
        # Ensure uuid exists before SQLAlchemy starts its work
        kwargs.setdefault("uuid", uuid7())
        super().__init__(**kwargs)


@declarative_mixin
class NanoidUniqueKey(SentinelMixin):

    nanoid: Mapped[str] = mapped_column(String(length=21), unique=True, sort_order=-100)
    """NanoID unique key column."""


@declarative_mixin
class SnowflakeUniqueKey(SentinelMixin):

    snowflake_id: Mapped[int] = mapped_column(unique=True, sort_order=-100)
    """Snowflake ID unique key column."""


@declarative_mixin
class UpdatedByColumn:

    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", use_alter=True, ondelete="SET NULL"),
        default=get_current_userid,
        onupdate=get_current_userid,
    )

    @declared_attr
    def updated_by(cls) -> Mapped["User"]:
        # kwargs = {}
        # with User class, the relationship becomes self-reference/adjacency list hence
        # needs remote_side to establish the correct many-to-one relationship
        # if self.__name__ == "User":
        #    kwargs["remote_side"] = [self.id]
        # return relationship(
        #    "User", uselist=False, foreign_keys=self.lastuser_id, **kwargs
        # )
        return relationship(
            "User",
            uselist=False,
            foreign_keys=[cls.updated_by_id],
            remote_side="User.id",
            cascade="save-update, merge",
            lazy="joined",
        )

    @cached_property
    def updated_by_login(self) -> str:
        return self.updated_by.login if self.updated_by else "-"


def AttachedFiles(storage_backend: str) -> Type:

    @declarative_mixin
    class _AttachedFiles:

        __storage_backend__ = storage_backend

        files: Mapped[Optional[FileObjectList]] = mapped_column(
            StoredObject(backend=storage_backend, multiple=True), nullable=True
        )

        @classmethod
        def get_storage_backend(cls) -> str:
            return cls.__storage_backend__

        def get_fileobject_storage_path(self, filename: str = "") -> str:
            # generate a file path for the given uuid using the first 2 characters as subdirectories
            class_name = self.__class__.__name__.lower()
            uuid = str(self.uuid)
            filename = filename or (fastnanoid.generate(size=8) + "-db")
            return f"{class_name}/{uuid[-2:]}/{uuid[2:4]}/{uuid}/{filename}", filename

        def set_fileobject_metadata(
            self,
            filename: str,  # original filename
            content_type: str,  # http content type
            category: str = "",  # category tag
            description: str = "",  # description of the file
            updated_by_id: int = 0,  # user id of the updater, for now set to 0
            updated_at: int = 0,  # timestamp of the update as integer epoch UTC
        ) -> dict[str, str]:
            return dict(
                filename=filename,
                content_type=content_type,
                category=category,
                description=description,
                updated_by_id=updated_by_id,
                updated_at=updated_at or int(datetime.now(timezone.utc).timestamp()),
            )

    return _AttachedFiles


@declarative_mixin
class HelperMethodMixin:
    """
    Mixin to add helper methods to models
    """

    @classmethod
    async def get(cls, dbt: AsyncSession, dbid: int | None = None, **kwargs) -> Self:
        """
        Get instance by ID or other unique fields
        """

        stmt = select(cls)
        if dbid is not None:
            stmt = stmt.where(cls.id == dbid)
        for key, value in kwargs.items():
            column = getattr(cls, key, None)
            if column is not None:
                stmt = stmt.where(column == value)
        result = await dbt.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_all(cls, dbt: AsyncSession, **kwargs) -> list[Self]:
        """
        Get all instances of the model
        """

        stmt = select(cls)
        for key, value in kwargs.items():
            column = getattr(cls, key, None)
            if column is not None:
                stmt = stmt.where(column == value)
        result = await dbt.execute(stmt)
        return result.scalars().all()


class RoleMixin:

    __viewing_roles__ = {r.SYSADM, r.SYSVIEW}
    __managing_roles__ = {r.SYSADM}
    __modifying_roles__ = {r.SYSADM}
    __deleting_roles__ = {r.SYSADM}

    # __managing_roles and __modifying_roles also infer __viewing_roles

    @hybrid_property
    def is_admin(self) -> bool:
        return getattr(self, "role", None) == "admin"

    @is_admin.expression
    def is_admin(cls):
        return cls.role == "admin"

    @classmethod
    def can_manage(cls, roles: set[str]) -> bool:
        return bool(cls.__managing_roles__ & roles)

    @classmethod
    def can_modify(cls, roles: set[str]) -> bool:
        return bool(cls.__modifying_roles__ & roles)

    @classmethod
    def can_view(cls, roles: set[str]) -> bool:
        return bool(cls.__viewing_roles__ & roles)

    @classmethod
    def can_delete(cls, roles: set[str]) -> bool:
        return cls.can_manage(cls, roles) or bool(cls.__deleting_roles__ & roles)


@declarative_mixin
class IdentityUUIDv7UserAuditBase(
    UUIDv7UniqueKey, IdentityAuditBase, UpdatedByColumn, HelperMethodMixin
):
    __abstract__ = True


@declarative_mixin
class IdentityUserAuditBase(IdentityAuditBase, UpdatedByColumn, HelperMethodMixin):
    __abstract__ = True


# note: need to create IdentityNanoidUserAuditBase as well
# EOF
