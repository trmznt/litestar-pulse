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
from litestar_pulse.db.models.account import UserDomain
from litestar_pulse.db.models.enumkey import EnumKey


class _InMemoryUpload:
    def __init__(
        self, filename: str, content: bytes, content_type: str = "text/plain"
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)
        self.file.name = "<memory>"


class TestUserDomainAttachmentCleanup(unittest.IsolatedAsyncioTestCase):
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

    async def _seed_userdomain(
        self, session: AsyncSession, domain_name: str
    ) -> UserDomain:
        category = EnumKey(
            key="@USERDOMAIN_TYPE", desc="Domain type", is_category=True, syskey=True
        )
        internal = EnumKey(
            key="Internal", desc="Internal", category=category, syskey=True
        )
        session.add_all([category, internal])
        await session.flush()

        instance = UserDomain(
            domain=domain_name,
            desc=domain_name,
            domain_type_id=internal.id,
        )
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    async def test_replacing_attachment_deletes_old_file(self) -> None:
        async with self.session_maker() as session:
            domain = await self._seed_userdomain(session, "replace.example")
            dbh = handler_factory(session)
            backend = storages.get_backend("lp_storage")

            first_upload = _InMemoryUpload("old.txt", b"old-content")
            await dbh.service.UserDomain.update_from_dict(
                domain, {"attachment": first_upload}
            )
            await session.commit()
            await session.refresh(domain)

            self.assertIsNotNone(domain.attachment)
            old_path = domain.attachment.path  # type: ignore[union-attr]
            self.assertEqual(backend.get_content(old_path), b"old-content")

            second_upload = _InMemoryUpload("new.txt", b"new-content")
            await dbh.service.UserDomain.update_from_dict(
                domain, {"attachment": second_upload}
            )
            await session.commit()
            await session.refresh(domain)

            self.assertIsNotNone(domain.attachment)
            new_path = domain.attachment.path  # type: ignore[union-attr]
            self.assertEqual(backend.get_content(new_path), b"new-content")

            with self.assertRaises(FileNotFoundError):
                backend.get_content(old_path)

    async def test_clearing_attachment_deletes_old_file(self) -> None:
        async with self.session_maker() as session:
            domain = await self._seed_userdomain(session, "clear.example")
            dbh = handler_factory(session)
            backend = storages.get_backend("lp_storage")

            upload = _InMemoryUpload("clear-me.txt", b"clear-me")
            await dbh.service.UserDomain.update_from_dict(
                domain, {"attachment": upload}
            )
            await session.commit()
            await session.refresh(domain)

            self.assertIsNotNone(domain.attachment)
            old_path = domain.attachment.path  # type: ignore[union-attr]
            self.assertEqual(backend.get_content(old_path), b"clear-me")

            await dbh.service.UserDomain.update_from_dict(domain, {"attachment": None})
            await session.commit()
            await session.refresh(domain)

            self.assertIsNone(domain.attachment)
            with self.assertRaises(FileNotFoundError):
                backend.get_content(old_path)


if __name__ == "__main__":
    unittest.main()
