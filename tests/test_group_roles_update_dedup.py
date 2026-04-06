# SPDX-FileCopyrightText: 2026 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from advanced_alchemy.base import orm_registry

from litestar_pulse.db import handler_factory
import litestar_pulse.db.handler as _handler_module  # noqa: F401
from litestar_pulse.db.models.account import Group, groups_roles
from litestar_pulse.db.models.enumkey import EnumKey, EnumKeyRegistry


class TestGroupRolesUpdateDedup(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "test.sqlite3"

        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(orm_registry.metadata.create_all)

    async def asyncTearDown(self) -> None:
        EnumKeyRegistry.clear()
        await self.engine.dispose()
        self.tmpdir.cleanup()

    async def _seed_group_with_roles(
        self, session: AsyncSession
    ) -> tuple[Group, EnumKey, EnumKey, EnumKey]:
        roles_category = EnumKey(
            key="@ROLES",
            desc="Roles category",
            is_category=True,
            syskey=True,
        )
        role_manage = EnumKey(
            key="GROUP_MANAGE",
            desc="Can manage groups",
            category=roles_category,
            syskey=True,
        )
        role_modify = EnumKey(
            key="GROUP_MODIFY",
            desc="Can modify groups",
            category=roles_category,
            syskey=True,
        )
        role_view = EnumKey(
            key="GROUP_VIEW",
            desc="Can view groups",
            category=roles_category,
            syskey=True,
        )
        session.add_all([roles_category, role_manage, role_modify, role_view])
        await session.flush()

        group = Group(name="ops", desc="Operations")
        group.roles = [role_manage, role_modify]
        session.add(group)
        await session.commit()
        await session.refresh(group)

        await EnumKeyRegistry.load_all(session)
        return group, role_manage, role_modify, role_view

    async def test_update_roles_with_existing_values_does_not_duplicate_association(
        self,
    ) -> None:
        async with self.session_maker() as session:
            group, role_manage, role_modify, role_view = (
                await self._seed_group_with_roles(session)
            )
            dbh = handler_factory(session)

            # Update includes already-assigned roles and one new role.
            await dbh.service.Group.update_from_dict(
                group,
                {"roles": [role_manage.id, role_modify.id, role_view.id]},
            )
            await session.commit()
            await session.refresh(group)

            rows = (
                await session.execute(
                    select(groups_roles.c.role_id).where(
                        groups_roles.c.group_id == group.id
                    )
                )
            ).all()
            role_ids_in_db = sorted(row[0] for row in rows)
            self.assertEqual(
                role_ids_in_db,
                sorted([role_manage.id, role_modify.id, role_view.id]),
            )
            self.assertEqual(len(rows), 3)

            # Sending duplicate ids in payload should still keep unique associations.
            await dbh.service.Group.update_from_dict(
                group,
                {"roles": [role_manage.id, role_manage.id, role_view.id]},
            )
            await session.commit()
            await session.refresh(group)

            rows_after_dup_payload = (
                await session.execute(
                    select(groups_roles.c.role_id).where(
                        groups_roles.c.group_id == group.id
                    )
                )
            ).all()
            role_ids_after_dup_payload = sorted(
                row[0] for row in rows_after_dup_payload
            )
            self.assertEqual(
                role_ids_after_dup_payload,
                sorted([role_manage.id, role_view.id]),
            )
            self.assertEqual(len(rows_after_dup_payload), 2)


if __name__ == "__main__":
    unittest.main()
