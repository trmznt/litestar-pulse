# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


import types
import yaml
from typing import Awaitable, TypeVar

from sqlalchemy import inspect, select
from sqlalchemy.orm import DeclarativeBase, undefer, joinedload, object_session

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from litestar.dto import DTOConfig
from litestar.plugins.sqlalchemy import SQLAlchemyDTO

# from litestar_pulse.lib.sqlalchemy_imports import SQLAlchemyDTO

from . import set_handler_class, handler_factory
from .models.meta import LPAsyncSession
from .models import account, enumkey  # noqa: F401

import lazy_object_proxy as lop

# repositories


class EnumKeyRepo(SQLAlchemyAsyncRepository[enumkey.EnumKey]):
    model_type = enumkey.EnumKey

    async def get_all_categories_for_options(self) -> Awaitable[list[tuple[int, str]]]:

        stmt = (
            select(enumkey.EnumKey.id, enumkey.EnumKey.key)
            .where(enumkey.EnumKey.category_id == None)  # noqa: E711
            .order_by(enumkey.EnumKey.key)
        )
        result = await self.session.execute(stmt)

        # Returns a list of Row objects (e.g., [(1, 'Category1'), (2, 'Category2')])
        return result.all()


class GroupDTO(SQLAlchemyDTO[account.Group]):
    """Data Transfer Object for Group model"""

    config = DTOConfig(
        max_nested_depth=1,
        exclude={"id"},
    )


class GroupRepo(SQLAlchemyAsyncRepository[account.Group]):
    model_type = account.Group

    async def get_all_for_options(self) -> Awaitable[list[tuple[int, str]]]:

        stmt = select(account.Group.id, account.Group.name).order_by(account.Group.name)
        result = await self.session.execute(stmt)

        # Returns a list of Row objects (e.g., [(1, 'Alice'), (2, 'Bob')])
        return result.all()


class UserDomainDTO(SQLAlchemyDTO[account.UserDomain]):
    """Data Transfer Object for UserDomain model"""

    config = DTOConfig(
        max_nested_depth=1,
        exclude={"id"},
    )


class UserDomainRepo(SQLAlchemyAsyncRepository[account.UserDomain]):
    model_type = account.UserDomain

    async def get_all_for_options(self) -> Awaitable[list[tuple[int, str]]]:

        stmt = select(account.UserDomain.id, account.UserDomain.domain).order_by(
            account.UserDomain.domain
        )
        result = await self.session.execute(stmt)

        return result.all()


class UserRepo(SQLAlchemyAsyncRepository[account.User]):
    model_type = account.User


class UserGroupRepo(SQLAlchemyAsyncRepository[account.UserGroup]):
    model_type = account.UserGroup


# services

T = TypeVar("T")


class LPBaseService(SQLAlchemyAsyncRepositoryService[T]):
    # this is a base service class that can be inherited by other services
    # it can be used to define common methods for all services

    async def before_update_from_dict(self, instance: T, data: dict) -> None:
        # this method can be overridden by inherited services to perform actions before updating from dict
        pass

    async def update_from_dict(self, instance: T, data: dict) -> T:

        if not object_session(instance):
            raise ValueError("Instance must be attached to a session before updating")

        # preprocess data before updating instance attributes
        await self.before_update_from_dict(instance, data)

        # update instance attributes from data dict
        for key, value in data.items():
            setattr(instance, key, value)

        state = inspect(instance)
        if state.pending or state.transient:
            # New objects are inserted by flush; repository.update() expects an existing row.
            await self.repository.session.flush()
        else:
            await self.repository.update(instance)

        return instance


class UserDomainService(LPBaseService[account.UserDomain]):
    model_type = account.UserDomain
    repository_type = UserDomainRepo


class GroupService(LPBaseService[account.Group]):
    model_type = account.Group
    repository_type = GroupRepo


class UserService(LPBaseService[account.User]):
    model_type = account.User
    repository_type = UserRepo

    async def before_update_from_dict(self, instance: account.User, data: dict) -> None:
        """Ensure the primary group is included in the user's groups before updating."""
        if "primarygroup_id" in data:
            primarygroup_id = data["primarygroup_id"]
            if primarygroup_id is not None:

                # Check if the user is already in this group
                usergroups = await instance.awaitable_attrs.usergroups
                if not any(ug.group_id == primarygroup_id for ug in usergroups):
                    # If not, add it to the user's groups
                    instance.usergroups.append(
                        account.UserGroup(group_id=primarygroup_id, role="M")
                    )


class UserDTO(SQLAlchemyDTO[account.User]):
    """Data Transfer Object for User model"""

    config = DTOConfig(
        max_nested_depth=1,
        exclude={"id"},
    )


class Model(types.SimpleNamespace):
    # this is inheritable to allow custom handlers to
    # override the model classes if needed
    EnumKey = enumkey.EnumKey
    Group = account.Group
    UserDomain = account.UserDomain
    UserGroup = account.UserGroup
    User = account.User


class Function(types.SimpleNamespace):
    undefer = staticmethod(undefer)
    joinedload = staticmethod(joinedload)


class DTO(types.SimpleNamespace):
    Group = GroupDTO
    UserDomain = UserDomainDTO
    User = UserDTO


class LPHandler:
    """
    This is a helper class for handling database operations
    """

    # inherited class can override the model namespace
    model = Model()
    func = Function()
    dto = DTO()

    def __init__(self, session: LPAsyncSession) -> None:
        self.session = session

        # prepare all AsyncRepos here, which will be specific for
        # each handler instance
        self.repo = types.SimpleNamespace()
        self.repo.EnumKey = lop.Proxy(lambda: EnumKeyRepo(session=self.session))
        self.repo.Group = lop.Proxy(lambda: GroupRepo(session=self.session))
        self.repo.UserDomain = lop.Proxy(lambda: UserDomainRepo(session=self.session))
        self.repo.User = lop.Proxy(lambda: UserRepo(session=self.session))
        self.repo.UserGroup = lop.Proxy(lambda: UserGroupRepo(session=self.session))

        # prepare all AsyncServices here, which will be specific for
        # each handler instance
        self.service = types.SimpleNamespace()
        self.service.UserDomain = lop.Proxy(
            lambda: UserDomainService(
                session=self.session, repository=self.repo.UserDomain.__wrapped__
            )
        )
        self.service.Group = lop.Proxy(
            lambda: GroupService(
                session=self.session, repository=self.repo.Group.__wrapped__
            )
        )
        self.service.User = lop.Proxy(
            lambda: UserService(
                session=self.session, repository=self.repo.User.__wrapped__
            )
        )

    async def get(
        self, model: type[DeclarativeBase], id: int
    ) -> Awaitable[DeclarativeBase | None]:
        return await model.get(self.session, id)

    def get_repository(
        self, model_type: type[DeclarativeBase]
    ) -> SQLAlchemyAsyncRepository:
        try:
            return self.repo.__dict__[model_type.__name__]
        except KeyError:
            raise ValueError(f"No repository found for model type {model_type}")

    def get_service(
        self, model_type: type[DeclarativeBase]
    ) -> SQLAlchemyAsyncRepositoryService:
        try:
            return self.service.__dict__[model_type.__name__]
        except KeyError:
            raise ValueError(f"No service found for model type {model_type}")


# set default handler class
set_handler_class(LPHandler)


# EOF
