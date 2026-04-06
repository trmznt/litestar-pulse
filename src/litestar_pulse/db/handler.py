# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


import types
import logging
import yaml
import anyio
import shutil
from pathlib import Path
from collections.abc import Awaitable
from typing import Any, Awaitable, TypeVar

import fastnanoid

from sqlalchemy import inspect, select
from sqlalchemy.orm import DeclarativeBase, undefer, joinedload, object_session
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm.attributes import flag_modified

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from advanced_alchemy.types.file_object import FileObject, FileObjectList
from advanced_alchemy.extensions.litestar import SQLAlchemyDTO

from litestar.dto import DTOConfig

from . import set_handler_class, handler_factory, get_handler
from .models.meta import LPAsyncSession
from .models import account, enumkey, fileobjects  # noqa: F401
from ..lib.fileupload import FileUploadProxy

import lazy_object_proxy as lop

logger = logging.getLogger(__name__)

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
            # handle MutableList fields with in-place mutation to ensure
            # SQLAlchemy change tracking works correctly
            mapper_relationships = inspect(instance).mapper.relationships
            for key, value in data.items():
                if not hasattr(instance, key):
                    # Allow hook-produced auxiliary keys without breaking updates
                    # for models that don't expose that attribute.
                    continue

                relationship = mapper_relationships.get(key)
                if (
                    relationship is not None
                    and relationship.uselist
                    and isinstance(value, list)
                ):
                    if not value:
                        relation_collection = getattr(instance, key)
                        relation_collection[:] = []
                        continue

                    if all(hasattr(item, "id") for item in value):
                        related_ids = self.normalize_unique_int_ids(
                            [getattr(item, "id") for item in value]
                        )
                        await self.reconcile_relation_collection_by_ids(
                            instance=instance,
                            attr_name=key,
                            related_model=relationship.mapper.class_,
                            related_ids=related_ids,
                        )
                        continue

                field = getattr(instance, key)
                if isinstance(field, MutableList):
                    field[:] = value
                    field.changed()
                    flag_modified(instance, key)
                else:
                    setattr(instance, key, value)
                    if isinstance(value, (list, MutableList)):
                        flag_modified(instance, key)

        state = inspect(instance)
        if state.pending or state.transient:
            # New objects are inserted by flush; repository.update() expects an existing row.
            await self.repository.session.flush()
        else:
            await self.repository.update(instance)

        return instance

    def normalize_unique_int_ids(self, raw_ids: Any) -> list[int]:
        """Normalize scalar/list ids to unique integer ids while preserving order."""

        if raw_ids in (None, ""):
            return []
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]

        normalized_ids: list[int] = []
        seen_ids: set[int] = set()
        for raw_id in raw_ids:
            if raw_id in (None, ""):
                continue
            normalized_id = int(raw_id)
            if normalized_id not in seen_ids:
                seen_ids.add(normalized_id)
                normalized_ids.append(normalized_id)
        return normalized_ids

    async def reconcile_relation_collection_by_ids(
        self,
        instance: Any,
        attr_name: str,
        related_model: type[DeclarativeBase],
        related_ids: list[int],
        valid_ids: set[int] | None = None,
    ) -> None:
        """Reconcile a relationship collection using session-local related objects.

        This avoids duplicate association inserts that can happen when assigning
        relationship values resolved from a different session/identity map.
        """

        if valid_ids is not None:
            invalid_ids = set(related_ids) - valid_ids
            if invalid_ids:
                raise ValueError(
                    f"One or more invalid IDs provided for {attr_name}: {invalid_ids}"
                )

        current_items = list(await getattr(instance.awaitable_attrs, attr_name))
        current_by_id = {item.id: item for item in current_items}

        missing_ids = [
            item_id for item_id in related_ids if item_id not in current_by_id
        ]
        missing_by_id: dict[int, Any] = {}
        if missing_ids:
            result = await self.repository.session.scalars(
                select(related_model).where(related_model.id.in_(missing_ids))
            )
            missing_items = result.all()
            missing_by_id = {item.id: item for item in missing_items}

        unresolved_ids = [
            item_id for item_id in missing_ids if item_id not in missing_by_id
        ]
        if unresolved_ids:
            raise ValueError(
                f"One or more IDs not found for {attr_name}: {set(unresolved_ids)}"
            )

        reconciled_items = [
            current_by_id.get(item_id) or missing_by_id[item_id]
            for item_id in related_ids
        ]

        relation_collection = getattr(instance, attr_name)
        relation_collection[:] = reconciled_items

    # generic file upload handling methods that can be used by inherited services

    async def _save_file_object_from_source_path(
        self, file_object: FileObject, source_path: str
    ) -> None:
        """Persist file content from local source path without loading full bytes into memory."""

        backend = file_object.backend
        if hasattr(backend, "fs") and hasattr(backend, "_prepare_path"):
            full_path = str(backend._prepare_path(file_object.path))
            logger.info(
                "FileObject save via source_path/fsspec put_file: source=%s dest=%s",
                source_path,
                full_path,
            )
            if "://" not in full_path:
                src = Path(source_path)
                dst = Path(full_path)

                def _mkdir() -> None:
                    dst.parent.mkdir(parents=True, exist_ok=True)

                await anyio.to_thread.run_sync(_mkdir)
                await anyio.to_thread.run_sync(shutil.copy2, src, dst)
            else:
                await anyio.to_thread.run_sync(
                    backend.fs.put_file, str(source_path), full_path
                )

            # Keep commonly used metadata fields in sync when available.
            try:
                info = await anyio.to_thread.run_sync(backend.fs.info, full_path)
                if isinstance(info, dict) and "size" in info:
                    file_object.size = int(info["size"])
            except Exception:
                # Metadata refresh failures should not fail the upload itself.
                pass
            return

        logger.info(
            "FileObject save via source_path/file_object.save_async fallback: source=%s path=%s",
            source_path,
            file_object.path,
        )
        file_object.source_path = str(source_path)
        await file_object.save_async()

    async def create_file_object(self, instance: Any, uploaded_file: Any) -> FileObject:
        # create a FileObject from the given uploaded file

        to_filename, _ = instance.get_fileobject_storage_path()
        if isinstance(uploaded_file, FileUploadProxy):
            logger.info(
                "create_file_object using FileUploadProxy source path: filename=%s path=%s",
                uploaded_file.filename,
                uploaded_file.path,
            )
            file_object = FileObject(
                backend=instance.get_storage_backend(),
                filename=uploaded_file.filename,
                to_filename=to_filename,
                metadata=dict(
                    filename=uploaded_file.filename,
                    content_type="application/octet-stream",
                    description=getattr(uploaded_file, "description", "") or "",
                    category=getattr(uploaded_file, "category", "") or "",
                ),
            )
            await self._save_file_object_from_source_path(
                file_object, str(uploaded_file.path)
            )
            return file_object
        elif (
            isinstance(uploaded_file.file.name, str)
            and Path(uploaded_file.file.name).exists()
        ):
            logger.info(
                "create_file_object using uploaded file temp path: filename=%s path=%s",
                uploaded_file.filename,
                uploaded_file.file.name,
            )
            file_object = FileObject(
                backend=instance.get_storage_backend(),
                filename=uploaded_file.filename,
                to_filename=to_filename,
                metadata=dict(
                    filename=uploaded_file.filename,
                    content_type=uploaded_file.content_type,
                ),
            )
            await self._save_file_object_from_source_path(
                file_object, str(uploaded_file.file.name)
            )
            return file_object
        else:
            logger.info(
                "create_file_object using in-memory content fallback: filename=%s",
                uploaded_file.filename,
            )
            content = uploaded_file.file.read()
            file_object = FileObject(
                backend=instance.get_storage_backend(),
                filename=uploaded_file.filename,
                to_filename=to_filename,
                metadata=dict(
                    filename=uploaded_file.filename,
                    content_type=uploaded_file.content_type,
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
            if not hasattr(instance, attr_name):
                data.pop(attr_name, None)
                return

            # Ensure the previous value is loaded so SQLAlchemy tracks it in
            # `history.deleted` when attachment is replaced/cleared. The
            # FileObject listener relies on that history for auto-cleanup.
            old_attachment = getattr(instance, attr_name, None)

            file_attachment = data.pop(attr_name, None)
            if file_attachment:
                data[attr_name] = await self.create_file_object(
                    instance, file_attachment
                )
            else:
                data[attr_name] = None

            new_attachment = data[attr_name]
            if old_attachment is not None and old_attachment is not new_attachment:
                pending = self.repository.session.info.setdefault(
                    "_lp_pending_file_deletes", []
                )
                pending.append(old_attachment)

    async def update_fileobject_list(
        self, instance: Any, attr_name: str, data: dict[str, Any]
    ) -> None:
        # set a list of file attachments on the instance, ensuring
        # relationships are properly tracked for cleanup

        if attr_name in data:
            instance_file_objects: FileObjectList | None = getattr(
                instance, attr_name, None
            )
            if instance_file_objects is None:
                instance_file_objects = FileObjectList()

            instance_file_objects_indexed: dict[str, FileObject] = {}
            if instance_file_objects:
                for fo in instance_file_objects:
                    path = str(getattr(fo, "path", "") or "")
                    filename = str(getattr(fo, "filename", "") or "")
                    dbid = str(getattr(fo, "id", "") or "")
                    for key in (path, filename, dbid):
                        if key:
                            instance_file_objects_indexed[key] = fo

            fileuploadproxy_list = data.get(attr_name, [])
            new_files = []
            existing_files = []

            matched_existing = set()

            for fileuploadproxy in fileuploadproxy_list:
                if not getattr(fileuploadproxy, "selected", True):
                    # explicit unselected items are treated as removals
                    continue

                if fileuploadproxy.is_new_upload:
                    new_file_object = await self.create_file_object(
                        instance, fileuploadproxy
                    )
                    new_files.append(new_file_object)
                else:
                    fileobject = instance_file_objects_indexed.pop(
                        fileuploadproxy.upload_id
                    )
                    if fileobject is None:
                        raise ValueError(
                            f"FileObject with key {fileuploadproxy.upload_id} not found"
                        )

                    # Preserve per-item metadata edits coming from the form JSON.
                    metadata = dict(getattr(fileobject, "metadata", {}) or {})
                    metadata["description"] = (
                        getattr(fileuploadproxy, "description", "") or ""
                    )
                    metadata["category"] = (
                        getattr(fileuploadproxy, "category", "") or ""
                    )
                    fileobject.metadata = metadata

                    existing_files.append(fileobject)

            merged_files = existing_files + new_files
            instance_file_objects[:] = merged_files
            if isinstance(instance_file_objects, MutableList):
                instance_file_objects.changed()
                data[attr_name] = instance_file_objects
            else:
                data[attr_name] = FileObjectList(merged_files)

            for deleted_fileobject in instance_file_objects_indexed.values():
                pending = self.repository.session.info.setdefault(
                    "_lp_pending_file_deletes", []
                )
                pending.append(deleted_fileobject)
            setattr(instance, attr_name, instance_file_objects)
            flag_modified(instance, attr_name)


class EnumKeyService(LPBaseService[enumkey.EnumKey]):
    model_type = enumkey.EnumKey
    repository_type = EnumKeyRepo


class UserDomainService(LPBaseService[account.UserDomain]):
    model_type = account.UserDomain
    repository_type = UserDomainRepo

    async def before_update_from_dict(
        self, instance: account.UserDomain, data: dict
    ) -> None:

        if "files" in data:
            await self.update_fileobject_list(instance, "files", data)


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
            role_ids = self.normalize_unique_int_ids(data["roles"])
            enumkeys = enumkey.EnumKeyRegistry.get_all_items("@ROLES")
            valid_role_ids = {int(ek[0]) for ek in enumkeys}

            await self.reconcile_relation_collection_by_ids(
                instance=instance,
                attr_name="roles",
                related_model=enumkey.EnumKey,
                related_ids=role_ids,
                valid_ids=valid_role_ids,
            )

            data.pop("roles", None)


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
            await self.set_file_object(instance, "attachment", data)


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
