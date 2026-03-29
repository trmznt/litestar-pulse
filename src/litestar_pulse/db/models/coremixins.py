# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from contextvars import ContextVar
from typing import TYPE_CHECKING, Self
from datetime import date, datetime
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

from litestar_pulse.lib import roles as r

if TYPE_CHECKING:
    from .account import User


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
