# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from uuid import UUID
from typing import TYPE_CHECKING, Any, Self

import msgspec

from sqlalchemy import (
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    select,
    Table,
    Column,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    column_mapped_collection,
    foreign,
    mapped_column,
    relationship,
    column_property,
    deferred,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property


from advanced_alchemy.base import orm_registry
from advanced_alchemy.types import JsonB

from ...lib import roles as r
from .enumkey import EnumKey, enumkey_proxy
from .coremixins import IdentityUUIDv7UserAuditBase, IdentityUserAuditBase, RoleMixin

if TYPE_CHECKING:  # pragma: no cover - typing helpers only
    pass


def _create_user_group(user: "User", role: str = "M") -> "UserGroup":
    """Factory for the `Group.users` association proxy."""

    return UserGroup(user=user, role=role)


class UserDomain(IdentityUUIDv7UserAuditBase, RoleMixin):
    __tablename__ = "userdomains"

    __managing_roles__ = RoleMixin.__managing_roles__ | {
        r.USERDOMAIN_CREATE,
        r.USERDOMAIN_MODIFY,
        r.USERDOMAIN_DELETE,
    }
    __viewing_roles__ = RoleMixin.__viewing_roles__ | {r.USERDOMAIN_VIEW}
    __modifying_roles__ = RoleMixin.__modifying_roles__ | {r.USERDOMAIN_MODIFY}

    domain: Mapped[str] = mapped_column(String(length=16), unique=True, nullable=False)
    desc: Mapped[str] = mapped_column(
        String(length=64), nullable=False, server_default=""
    )
    referer: Mapped[str] = mapped_column(
        String(length=128), nullable=False, server_default=""
    )
    autoadd: Mapped[bool] = mapped_column(
        nullable=False, server_default="0", default=False
    )
    credscheme: Mapped[dict[str, Any] | None] = mapped_column(
        JsonB,
        nullable=False,
        server_default="null",
    )
    flags: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="domain",
        cascade="all, delete, delete-orphan",
        foreign_keys="User.domain_id",
    )

    domain_type_id: Mapped[int] = mapped_column(
        ForeignKey("enumkeys.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    domain_type = enumkey_proxy("domain_type_id", "@USERDOMAIN_TYPE")

    def __repr__(self) -> str:
        return f"<UserDomain id={self.id} domain={self.domain}>"

    def __str__(self) -> str:
        return self.domain


class UserData(IdentityUserAuditBase, RoleMixin):

    __tablename__ = "userdatas"

    __managing_roles__ = RoleMixin.__managing_roles__ | {
        r.USER_CREATE,
        r.USER_MODIFY,
        r.USER_DELETE,
    }
    __viewing_roles__ = RoleMixin.__viewing_roles__ | {r.USER_VIEW}
    __modifying_roles__ = RoleMixin.__modifying_roles__ | {r.USER_MODIFY}

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_id: Mapped[int] = mapped_column(
        ForeignKey("enumkeys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bindata: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mimetype: Mapped[str] = mapped_column(String(32), nullable=False)

    user: Mapped["User"] = relationship(
        "User",
        back_populates="userdata",
        foreign_keys=[user_id],
    )


class UserGroup(IdentityUserAuditBase, RoleMixin):

    __tablename__ = "users_groups"
    __table_args__ = (UniqueConstraint("user_id", "group_id"),)

    __managing_roles__ = RoleMixin.__managing_roles__ | {
        r.GROUP_ADDUSER,
        r.GROUP_DELUSER,
    }
    __viewing_roles__ = RoleMixin.__viewing_roles__ | {r.GROUP_VIEW}
    __modifying_roles__ = RoleMixin.__modifying_roles__ | {
        r.GROUP_ADDUSER,
        r.GROUP_DELUSER,
    }

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    # for role: M: member, A: admin
    role: Mapped[str] = mapped_column(String(1), nullable=False, server_default="M")

    user: Mapped[User] = relationship(
        "User",
        back_populates="groups",
        foreign_keys=[user_id],
    )
    group: Mapped[Group] = relationship(
        "Group",
        back_populates="usergroups",
        foreign_keys=[group_id],
    )


class User(IdentityUUIDv7UserAuditBase, RoleMixin):
    __tablename__ = "users"

    __managing_roles__ = RoleMixin.__managing_roles__ | {
        r.USER_CREATE,
        r.USER_MODIFY,
        r.USER_DELETE,
    }
    __viewing_roles__ = RoleMixin.__viewing_roles__ | {r.USER_VIEW}
    __modifying_roles__ = RoleMixin.__modifying_roles__ | {r.USER_MODIFY}

    login: Mapped[str] = mapped_column(String(length=32), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(
        String(length=48), unique=True, index=True, nullable=False
    )
    lastname: Mapped[str] = mapped_column(
        String(length=64), nullable=False, server_default=""
    )
    firstname: Mapped[str] = mapped_column(
        String(length=64), nullable=False, server_default=""
    )
    credential: Mapped[str] = mapped_column(
        String(length=255), nullable=False, server_default=""
    )
    name = column_property(lastname + ", " + firstname)

    institution: Mapped[str] = mapped_column(
        String(length=128), nullable=False, server_default=""
    )
    address: Mapped[str] = mapped_column(
        String(length=128), nullable=False, server_default=""
    )
    contact: Mapped[str] = mapped_column(
        String(length=32), nullable=False, server_default=""
    )
    status: Mapped[bool] = mapped_column(
        nullable=False, server_default="1", default=True
    )
    flags: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
    )
    data: Mapped[dict] = mapped_column(JsonB, nullable=False, server_default="{}")

    domain_id: Mapped[int] = mapped_column(ForeignKey("userdomains.id"), nullable=False)
    domain: Mapped[UserDomain] = relationship(
        back_populates="users",
        foreign_keys=[domain_id],
        primaryjoin=foreign(domain_id) == UserDomain.id,
        lazy="joined",
    )

    primarygroup_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id"), nullable=False, index=True
    )
    primarygroup: Mapped["Group"] = relationship(
        "Group",
        back_populates="primaryusers",
        foreign_keys=[primarygroup_id],
        uselist=False,
        lazy="joined",
    )

    userdata: Mapped[dict[int, UserData]] = relationship(
        "UserData",
        collection_class=column_mapped_collection(UserData.key_id),
        cascade="all, delete, delete-orphan",
        foreign_keys=[UserData.user_id],
        back_populates="user",
    )

    groups: Mapped[list[UserGroup]] = relationship(
        UserGroup,
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys=[UserGroup.user_id],
        # lazy="joined", cannot do joined loading here because of the association proxy,
        # will cause circular loading
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} login={self.login} email={self.email} domain_id={self.domain_id}>"

    def __str__(self) -> str:
        return f"{self.login}/{self.domain.domain}"

    @classmethod
    async def get_by_login(cls, session: AsyncSession, login: str) -> Self | None:
        stmt = select(cls).where(cls.login == login)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def user_instance(self) -> UserInstance:
        return UserInstance(
            id=self.id,
            uuid=self.uuid,
            login=self.login,
            domain=(await self.awaitable_attrs.domain).domain,
            name=self.name,
            roles=[],
            groups=[],
        )


groups_roles = Table(
    "groups_roles",
    orm_registry.metadata,
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("enumkeys.id", ondelete="CASCADE"), primary_key=True),
)


class Group(IdentityUUIDv7UserAuditBase, RoleMixin):

    __tablename__ = "groups"

    __managing_roles__ = RoleMixin.__managing_roles__ | {
        r.GROUP_CREATE,
        r.GROUP_MODIFY,
        r.GROUP_DELETE,
        r.GROUP_ADDUSER,
        r.GROUP_DELUSER,
    }
    __viewing_roles__ = RoleMixin.__viewing_roles__ | {r.GROUP_VIEW}
    __modifying_roles__ = RoleMixin.__modifying_roles__ | {
        r.GROUP_MODIFY,
        r.GROUP_ADDUSER,
        r.GROUP_DELUSER,
    }

    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    desc: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    scheme: Mapped[dict[str, Any] | None] = mapped_column(
        JsonB,
        nullable=False,
        server_default="null",
    )
    flags: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
    )

    roles: Mapped[list[EnumKey]] = relationship(
        EnumKey,
        secondary=groups_roles,
        # primaryjoin=lambda: Group.id == groups_roles.c.group_id,
        # secondaryjoin=lambda: EnumKey.id == groups_roles.c.role_id,
        order_by=lambda: EnumKey.key,
    )

    primaryusers: Mapped[list[User]] = relationship(
        User,
        back_populates="primarygroup",
        foreign_keys=User.primarygroup_id,
    )

    usergroups: Mapped[list[UserGroup]] = relationship(
        UserGroup,
        back_populates="group",
        cascade="all, delete-orphan",
        foreign_keys=[UserGroup.group_id],
    )

    associated_groups: Mapped[list["AssociatedGroup"]] = relationship(
        "AssociatedGroup",
        foreign_keys="AssociatedGroup.group_id",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    associated_to: Mapped[list["AssociatedGroup"]] = relationship(
        "AssociatedGroup",
        foreign_keys="AssociatedGroup.assoc_group_id",
        back_populates="associated_group",
        cascade="all, delete-orphan",
    )

    users = association_proxy("usergroups", "user", creator=_create_user_group)

    def __repr__(self) -> str:
        return f"<Group id={self.id} name={self.name}>"

    def __str__(self) -> str:
        return self.name


class AssociatedGroup(IdentityUserAuditBase):

    __tablename__ = "associated_groups"
    __table_args__ = (UniqueConstraint("group_id", "assoc_group_id"),)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    assoc_group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(1), nullable=False, server_default="R")

    group: Mapped[Group] = relationship(
        "Group",
        foreign_keys=[group_id],
        back_populates="associated_groups",
    )
    associated_group: Mapped[Group] = relationship(
        "Group",
        foreign_keys=[assoc_group_id],
        back_populates="associated_to",
    )


class UserInstance(msgspec.Struct):
    """
    UserInstance is a pickled-able instance that can be transported between processes or services
    """

    id: int
    uuid: UUID
    login: str
    domain: str
    name: str
    roles: list[str]
    groups: list[str]

    def is_sysadm(self) -> bool:
        raise NotImplementedError()

    def in_group(self, groups: list[str]) -> bool:
        raise NotImplementedError()

    def has_roles(self, roles: list[str]) -> bool:
        raise NotImplementedError()

    def groups(self) -> list[str]:
        raise NotImplementedError()

    def check_consistency(self, update: bool = False) -> bool:
        raise NotImplementedError()


UserDomain.user_count: Mapped[int] = deferred(
    column_property(
        select(func.count(User.id))
        .where(User.domain_id == UserDomain.id)
        .correlate_except(User)
        .scalar_subquery()
    )
)

# EOF
