# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


import types
import yaml
from pathlib import Path
from collections.abc import Awaitable
from typing import Any, Awaitable, TypeVar

import fastnanoid

from sqlalchemy import inspect, select
from sqlalchemy.orm import DeclarativeBase, undefer, joinedload, object_session

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from advanced_alchemy.types.file_object import FileObject

from litestar.dto import DTOConfig
from litestar.plugins.sqlalchemy import SQLAlchemyDTO

# from litestar_pulse.lib.sqlalchemy_imports import SQLAlchemyDTO

from . import set_handler_class, handler_factory, get_handler
from .models.meta import LPAsyncSession
from .models import account, enumkey, fileobjects  # noqa: F401

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


class FileAttachmentRepo(SQLAlchemyAsyncRepository[fileobjects.FileAttachment]):
    model_type = fileobjects.FileAttachment


class FileObjectRepo(SQLAlchemyAsyncRepository[fileobjects.FileObject]):
    model_type = fileobjects.FileObject

    async def get_all_for_options(self) -> Awaitable[list[tuple[int, str]]]:
        stmt = select(fileobjects.FileObject.id, fileobjects.FileObject.path).order_by(
            fileobjects.FileObject.path
        )
        result = await self.session.execute(stmt)
        return result.all()


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

        # Prevent query-invoked autoflush while hooks may issue SELECTs
        # before required attributes are assigned on new/pending instances.
        with self.repository.session.no_autoflush:
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

    # generic file upload handling methods that can be used by inherited services

    def generate_storage_path(self, uuid: str) -> str:
        # generate a file path for the given uuid using the first 2 characters as subdirectories
        class_name = self.repository.model_type.__name__.lower()
        return (
            f"{class_name}/{uuid[-2:]}/{uuid[2:4]}/{uuid}/{fastnanoid.generate(size=8)}"
        )

    async def create_file_object(self, uploaded_file: Any, uuid: str) -> FileObject:
        # create a FileObject from the given uploaded file
        uuid = str(uuid)
        if (
            isinstance(uploaded_file.file.name, str)
            and Path(uploaded_file.file.name).exists()
        ):
            file_object = FileObject(
                backend="lp_storage",
                filename=self.generate_storage_path(uuid),
                metadata=dict(
                    filename=uploaded_file.filename,
                    content_type=uploaded_file.content_type,
                ),
                source_path=uploaded_file.file.name,
            )
        else:
            content = uploaded_file.file.read()
            file_object = FileObject(
                backend="lp_storage",
                filename=self.generate_storage_path(uuid),
                metadata=dict(
                    filename=uploaded_file.filename,
                    content_type=uploaded_file.content_type,
                    source_path=uploaded_file.file.name,
                ),
                content=content,
            )
        await file_object.save_async()
        return file_object

    async def set_file_object(
        self, instance: Any, attr_name: str, data: dict[str, Any]
    ) -> None:
        # set the file attachment on the instance, ensuring the relationship is properly tracked for cleanup

        if attr_name in data:
            # Ensure the previous value is loaded so SQLAlchemy tracks it in
            # `history.deleted` when attachment is replaced/cleared. The
            # FileObject listener relies on that history for auto-cleanup.
            old_attachment = getattr(instance, attr_name, None)

            file_attachment = data[attr_name]
            if file_attachment:
                data[attr_name] = await self.create_file_object(
                    file_attachment, instance.uuid
                )
            else:
                data[attr_name] = None

            new_attachment = data[attr_name]
            if old_attachment is not None and old_attachment is not new_attachment:
                pending = self.repository.session.info.setdefault(
                    "_lp_pending_file_deletes", []
                )
                pending.append(old_attachment)


class EnumKeyService(LPBaseService[enumkey.EnumKey]):
    model_type = enumkey.EnumKey
    repository_type = EnumKeyRepo


class UserDomainService(LPBaseService[account.UserDomain]):
    model_type = account.UserDomain
    repository_type = UserDomainRepo

    async def before_update_from_dict(
        self, instance: account.UserDomain, data: dict
    ) -> None:

        if "attachment" in data:
            await self.set_file_object(instance, "attachment", data)


class GroupService(LPBaseService[account.Group]):
    model_type = account.Group
    repository_type = GroupRepo

    async def before_update_from_dict(
        self, instance: account.Group, data: dict
    ) -> None:
        """
        Perform the following before updating a Group instance from a dict:
        - convert the "roles" key from a list of integer primary key ids to the EnumKey
          instances
        """

        if "roles" in data:
            role_ids = data["roles"]
            # Convert role IDs to EnumKey instances
            roles = []

            # check that all role IDs are under ROLES category
            enumkeys = enumkey.EnumKeyRegistry.get_all_items("@ROLES")
            valid_role_ids = {ek[0] for ek in enumkeys}
            if any(role_id_diff := set(role_ids) - valid_role_ids):
                raise ValueError(
                    f"One or more invalid role IDs provided: {role_id_diff}"
                )

            roles = await get_handler().repo.EnumKey.list(
                enumkey.EnumKey.id.in_(role_ids)
            )

            data["roles"] = roles


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

        if "attachment" in data:
            file_attachment = data["attachment"]
            if file_attachment:
                data["attachment"] = await self.create_file_object(file_attachment)


class FileAttachmentService(LPBaseService[fileobjects.FileAttachment]):
    model_type = fileobjects.FileAttachment
    repository_type = FileAttachmentRepo


class FileObjectService(LPBaseService[fileobjects.FileObject]):
    model_type = fileobjects.FileObject
    repository_type = FileObjectRepo


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
    FileAttachment = fileobjects.FileAttachment
    FileObject = fileobjects.FileObject


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
        self.repo.FileAttachment = lop.Proxy(
            lambda: FileAttachmentRepo(session=self.session)
        )
        self.repo.FileObject = lop.Proxy(lambda: FileObjectRepo(session=self.session))

        # prepare all AsyncServices here, which will be specific for
        # each handler instance
        self.service = types.SimpleNamespace()
        self.service.EnumKey = lop.Proxy(
            lambda: EnumKeyService(
                session=self.session, repository=self.repo.EnumKey.__wrapped__
            )
        )
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
        self.service.FileAttachment = lop.Proxy(
            lambda: FileAttachmentService(
                session=self.session, repository=self.repo.FileAttachment.__wrapped__
            )
        )
        self.service.FileObject = lop.Proxy(
            lambda: FileObjectService(
                session=self.session, repository=self.repo.FileObject.__wrapped__
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
