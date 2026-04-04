# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from advanced_alchemy._listeners import setup_file_object_listeners
from advanced_alchemy.base import orm_registry
from advanced_alchemy.types.file_object import storages

from litestar_pulse.config.filestorage import TMP_UPLOAD_DIR, init_filestorage
from litestar_pulse.db import handler_factory
import litestar_pulse.db.handler as _handler_module  # noqa: F401
from litestar_pulse.db.models.account import UserDomain
from litestar_pulse.db.models.enumkey import EnumKey
from litestar_pulse.lib.fileupload import FileUploadProxy, get_upload_path


class _InMemoryUpload:
    def __init__(
        self, filename: str, content: bytes, content_type: str = "text/plain"
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(content)
        self.file.name = "<memory>"


class TestUserDomainFileObjectListUpdate(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
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

    async def test_add_new_file_when_list_already_populated(self) -> None:
        async with self.session_maker() as session:
            domain = await self._seed_userdomain(session, "files-list-update.example")
            dbh = handler_factory(session)
            backend = storages.get_backend("lp_storage")

            # Seed one existing stored file object on the model.
            old_upload = _InMemoryUpload("existing.txt", b"existing-content")
            old_file = await dbh.service.UserDomain.create_file_object(
                domain, old_upload
            )
            domain.files = [old_file]
            await session.commit()
            await session.refresh(domain)

            self.assertTrue(domain.files)
            old_path = domain.files[0].path
            self.assertEqual(backend.get_content(old_path), b"existing-content")

            # Build a FileUploadProxy for a new upload id and create temp upload file.
            fake_request = SimpleNamespace(
                user=SimpleNamespace(uuid=domain.uuid),
                scope={"_session_id": "session-test-1"},
                cookies={},
            )
            new_proxy = FileUploadProxy(
                upload_id="new-file-123-upload",
                filename="new.txt",
                request=fake_request,
                selected=True,
            )
            new_upload_path = Path(new_proxy.path)
            new_upload_path.parent.mkdir(parents=True, exist_ok=True)
            new_upload_path.write_bytes(b"new-content")

            # Keep existing file selected by referencing it using its persisted path.
            existing_proxy = FileUploadProxy(
                upload_id=old_path,
                filename="existing.txt",
                request=fake_request,
                selected=True,
            )

            await dbh.service.UserDomain.update_from_dict(
                domain,
                {"files": [existing_proxy, new_proxy]},
            )
            await session.commit()
            await session.refresh(domain)

            self.assertEqual(len(domain.files or []), 2)
            stored_paths = {f.path for f in (domain.files or [])}
            self.assertIn(old_path, stored_paths)

            new_file_candidates = [
                f
                for f in (domain.files or [])
                if f.metadata and f.metadata.get("filename") == "new.txt"
            ]
            self.assertEqual(len(new_file_candidates), 1)
            self.assertTrue(new_file_candidates[0].path)


if __name__ == "__main__":
    unittest.main()
