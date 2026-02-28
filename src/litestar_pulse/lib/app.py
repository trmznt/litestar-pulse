# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import os
import sys
from pathlib import Path
from collections.abc import AsyncGenerator

import ipdb

from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from litestar import Litestar
from litestar.exceptions import ClientException, NotFoundException
from litestar.plugins.sqlalchemy import SQLAlchemyAsyncConfig, SQLAlchemyInitPlugin

# from litestar_pulse.lib.sqlalchemy_imports import (
#    SQLAlchemyAsyncConfig,
#    SQLAlchemyInitPlugin,
# )
from litestar.status_codes import HTTP_409_CONFLICT
from litestar.middleware.session.server_side import (
    ServerSideSessionBackend,
    ServerSideSessionConfig,
)
from litestar.stores.file import FileStore
from litestar.plugins.flash import FlashPlugin
from litestar.static_files import create_static_files_router


from litestar_pulse.config.db import DBConfig
from litestar_pulse.config.app import (
    logging_config,
    session_config,
    template_config,
    flash_config,
    logger,
)
from litestar_pulse.db.models import account
from litestar_pulse.db.models.enumkey import EnumKeyRegistry
from litestar_pulse.lib.debugger import SelectiveDebugger
from litestar_pulse.lib.exceptions import handle_not_found, mako_html_exception_handler
from litestar_pulse.lib.auth import session_auth
from litestar_pulse.lib.utils import resources_to_paths


async def provide_transaction(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    try:
        async with db_session.begin():
            await EnumKeyRegistry.ensure_current(db_session)
            yield db_session
    except IntegrityError as exc:
        raise ClientException(
            status_code=HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


def init_app() -> Litestar:

    from litestar_pulse.views.home import HomeView

    from litestar_pulse.views.login import LoginView
    from litestar_pulse.views.enumkey import EnumKeyView
    from litestar_pulse.views.userdomain import UserDomainView
    from litestar_pulse.views.user import UserView
    from litestar_pulse.views.group import GroupView
    from litestar_pulse.views.api_v1 import API_v1

    dbc = DBConfig()
    dbplugin = SQLAlchemyInitPlugin(
        config=SQLAlchemyAsyncConfig(engine_instance=dbc.engine)
    )
    session_factory = dbc.session_factory

    async def preload_enumkeys() -> None:
        async with session_factory() as session:
            await EnumKeyRegistry.load_all(session)

    flash_plugin = FlashPlugin(config=flash_config)

    debugger = SelectiveDebugger(
        ipdb,
        excluded_exceptions=(NotFoundException,),
    )

    static_route_handler = create_static_files_router(
        path="/static/",
        directories=resources_to_paths(
            [
                "assets",
                "litestar_pulse:assets",
            ]
        ),
    )

    # when run in debug mode, use the following exception handlers
    if os.getenv("LITESTAR_DEBUG", "false").lower() in ("1", "true", "yes"):
        logger.info(
            "WARNING: DEBUG MODE IS ENABLED. This should NOT be used in production!"
        )
        exception_handlers = {
            NotFoundException: handle_not_found,
            Exception: mako_html_exception_handler,
        }
    else:
        exception_handlers = {
            NotFoundException: handle_not_found,
        }

    # when run in PDB mode, use the following debugger
    if os.getenv("LITESTAR_PDB", "false").lower() in ("1", "true", "yes"):
        logger.info(
            "WARNING: PDB on exception is ENABLED. This should NOT be used in production!"
        )
        pdb_on_exception = True
    else:
        pdb_on_exception = False

    return Litestar(
        route_handlers=[
            static_route_handler,
            HomeView,
            LoginView,
            EnumKeyView,
            UserDomainView,
            UserView,
            GroupView,
            API_v1,
        ],
        dependencies={"transaction": provide_transaction},
        middleware=[session_config.middleware],
        stores={"sessions": FileStore(path=Path("session_data"))},
        on_app_init=[session_auth.on_app_init],
        on_startup=[preload_enumkeys],
        debugger_module=debugger,
        pdb_on_exception=pdb_on_exception,
        logging_config=logging_config,
        template_config=template_config,
        plugins=[dbplugin, flash_plugin],
        exception_handlers=exception_handlers,
    )


# EOF
