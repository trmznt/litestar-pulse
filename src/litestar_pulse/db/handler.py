# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


import types
import yaml
from typing import Awaitable

from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, undefer, joinedload

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


class UserDomainService(SQLAlchemyAsyncRepositoryService[account.UserDomain]):
    model_type = account.UserDomain


class UserRepo(SQLAlchemyAsyncRepository[account.User]):
    model_type = account.User


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


class LPHandler:
    """
    This is a helper class for handling database operations
    """

    # inherited class can override the model namespace
    model = Model()
    func = Function()

    def __init__(self, session: LPAsyncSession) -> None:
        self.session = session

        # prepare all AsyncRepos here, which will be specific for
        # each handler instance
        self.repo = types.SimpleNamespace()
        self.repo.EnumKey = lop.Proxy(lambda: EnumKeyRepo(session=self.session))
        self.repo.Group = lop.Proxy(lambda: GroupRepo(session=self.session))
        self.repo.UserDomain = lop.Proxy(lambda: UserDomainRepo(session=self.session))
        self.repo.User = lop.Proxy(lambda: UserRepo(session=self.session))

        # prepare all AsyncServices here, which will be specific for
        # each handler instance
        self.service = types.SimpleNamespace()

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


# set default handler class
set_handler_class(LPHandler)


# EOF
