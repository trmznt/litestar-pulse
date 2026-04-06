# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from advanced_alchemy.base import orm_registry

from litestar_pulse.db.models import coremixins
from litestar_pulse.db.models.account import Group, User, UserDomain
from litestar_pulse.db.models.enumkey import EnumKey


class TestUserUpdatedByCircularDependency(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "test.sqlite3"

        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(orm_registry.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        self.tmpdir.cleanup()

    async def _seed_user(self, session: AsyncSession) -> User:
        category = EnumKey(
            key="@USERDOMAIN_TYPE", desc="Domain type", is_category=True, syskey=True
        )
        internal = EnumKey(
            key="Internal", desc="Internal", category=category, syskey=True
        )
        session.add_all([category, internal])
        await session.flush()

        domain = UserDomain(
            domain="audit-self.example",
            desc="audit-self.example",
            domain_type_id=internal.id,
        )
        session.add(domain)
        await session.flush()

        group = Group(name="audit-self-group", desc="Audit self group")
        session.add(group)
        await session.flush()

        user = User(
            login="audit-self-user",
            email="audit-self@example.test",
            lastname="Audit",
            firstname="Self",
            credential="x",
            domain_id=domain.id,
            primarygroup_id=group.id,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def test_user_update_with_self_updated_by_does_not_raise_circular_dependency(
        self,
    ) -> None:
        async with self.session_maker() as session:
            user = await self._seed_user(session)

            # Reproduce the self-referential audit scenario that used to trigger
            # CircularDependencyError on autoflush.
            token = coremixins._current_userid.set(user.id)
            try:
                user.firstname = "SelfUpdated"
                await session.flush()
                await session.commit()
            finally:
                coremixins._current_userid.reset(token)

            await session.refresh(user)
            self.assertEqual(user.firstname, "SelfUpdated")
            self.assertEqual(user.updated_by_id, user.id)


if __name__ == "__main__":
    unittest.main()
