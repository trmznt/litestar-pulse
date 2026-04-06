# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from advanced_alchemy._listeners import setup_file_object_listeners
from advanced_alchemy.base import orm_registry
from advanced_alchemy.types.file_object import storages

from litestar_pulse.config.filestorage import init_filestorage
from litestar_pulse.db import handler_factory
import litestar_pulse.db.handler as _handler_module  # noqa: F401
from litestar_pulse.db.models.account import Group, User, UserDomain
from litestar_pulse.db.models.enumkey import EnumKey


class _InMemoryUpload:
    def __init__(
        self, filename: str, content: bytes, content_type: str = "text/plain"
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)
        self.file.name = "<memory>"


class TestUserAttachmentCleanup(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Ensure lp_storage backend exists for StoredObject backend="lp_storage".
        init_filestorage()

    async def asyncSetUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "test.sqlite3"

        setup_file_object_listeners()
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(orm_registry.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        self.tmpdir.cleanup()

    async def _seed_user(self, session: AsyncSession, suffix: str) -> User:
        category = EnumKey(
            key="@USERDOMAIN_TYPE", desc="Domain type", is_category=True, syskey=True
        )
        internal = EnumKey(
            key="Internal", desc="Internal", category=category, syskey=True
        )
        session.add_all([category, internal])
        await session.flush()

        domain = UserDomain(
            domain=f"{suffix}.example",
            desc=f"{suffix}.example",
            domain_type_id=internal.id,
        )
        session.add(domain)
        await session.flush()

        group = Group(name=f"group-{suffix}", desc=f"group-{suffix}")
        session.add(group)
        await session.flush()

        user = User(
            login=f"user-{suffix}",
            email=f"user-{suffix}@example.test",
            lastname="Attachment",
            firstname="Test",
            credential="x",
            domain_id=domain.id,
            primarygroup_id=group.id,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def test_replacing_attachment_deletes_old_file(self) -> None:
        async with self.session_maker() as session:
            user = await self._seed_user(session, "replace")
            dbh = handler_factory(session)
            backend = storages.get_backend("lp_storage")

            first_upload = _InMemoryUpload("old.txt", b"old-content")
            await dbh.service.User.update_from_dict(user, {"attachment": first_upload})
            await session.commit()
            await session.refresh(user)

            self.assertIsNotNone(user.attachment)
            old_path = user.attachment.path  # type: ignore[union-attr]
            self.assertEqual(backend.get_content(old_path), b"old-content")

            second_upload = _InMemoryUpload("new.txt", b"new-content")
            await dbh.service.User.update_from_dict(user, {"attachment": second_upload})
            await session.commit()
            await session.refresh(user)

            self.assertIsNotNone(user.attachment)
            new_path = user.attachment.path  # type: ignore[union-attr]
            self.assertEqual(backend.get_content(new_path), b"new-content")

            with self.assertRaises(FileNotFoundError):
                backend.get_content(old_path)

    async def test_clearing_attachment_deletes_old_file(self) -> None:
        async with self.session_maker() as session:
            user = await self._seed_user(session, "clear")
            dbh = handler_factory(session)
            backend = storages.get_backend("lp_storage")

            upload = _InMemoryUpload("clear-me.txt", b"clear-me")
            await dbh.service.User.update_from_dict(user, {"attachment": upload})
            await session.commit()
            await session.refresh(user)

            self.assertIsNotNone(user.attachment)
            old_path = user.attachment.path  # type: ignore[union-attr]
            self.assertEqual(backend.get_content(old_path), b"clear-me")

            await dbh.service.User.update_from_dict(user, {"attachment": None})
            await session.commit()
            await session.refresh(user)

            self.assertIsNone(user.attachment)
            with self.assertRaises(FileNotFoundError):
                backend.get_content(old_path)


if __name__ == "__main__":
    unittest.main()
