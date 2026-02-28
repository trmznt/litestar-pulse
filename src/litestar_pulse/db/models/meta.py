# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from typing import TYPE_CHECKING, Callable
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

# dbs = database sessions
# dbh = database handlers
# dbc = database connections


class LPAsyncSession(AsyncSession):
    pass


# EOF
