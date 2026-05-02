# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from litestar_pulse.views import get_lp_controllers

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import os
from pathlib import Path
from collections.abc import AsyncGenerator, Callable
from functools import cache
from typing import Any

import ipdb
import yaml

from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from advanced_alchemy.extensions.litestar import (
    SQLAlchemyPlugin,
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
)

from litestar import Litestar, get
from litestar.middleware import DefineMiddleware
from litestar.exceptions import (
    ClientException,
    NotAuthorizedException,
    NotFoundException,
)

# from litestar_pulse.lib.sqlalchemy_imports import (
#    SQLAlchemyAsyncConfig,
#    SQLAlchemyInitPlugin,
# )
from litestar.status_codes import HTTP_409_CONFLICT, HTTP_204_NO_CONTENT
from litestar.middleware.session.server_side import (
    ServerSideSessionBackend,
    ServerSideSessionConfig,
)
from litestar.stores.file import FileStore
from litestar.plugins.flash import FlashPlugin
from litestar.static_files import create_static_files_router

from debug_toolbar.litestar import DebugToolbarPlugin, LitestarDebugToolbarConfig

# from litestar_pulse.config.db import DBConfig
from litestar_pulse.config.db_aa import alchemy_config
from litestar_pulse.config.app import (
    logging_config,
    session_config,
    template_config,
    flash_config,
    logger,
    general_config,
)
from litestar_pulse.config.filestorage import init_filestorage
from litestar_pulse.db.models import account
from litestar_pulse.db.models.enumkey import EnumKeyRegistry
from litestar_pulse.lib.debugger import SelectiveDebugger
from litestar_pulse.lib.exceptions import (
    handle_not_found,
    auth_exception_handler,
    mako_html_exception_handler,
)
from litestar_pulse.lib.auth import session_auth
from litestar_pulse.lib.middleware import HandlerContextMiddleware
from litestar_pulse.lib.utils import resources_to_paths
from litestar_pulse.lib.template import context_injector


async def provide_transaction(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncSession, None]:
    session_info = db_session.sync_session.info
    try:
        async with db_session.begin():
            await EnumKeyRegistry.ensure_current(db_session)
            yield db_session

        pending_deletes = session_info.pop("_lp_pending_file_deletes", [])
        if pending_deletes:
            logger.debug(
                "Post-commit attachment cleanup queue size: %d",
                len(pending_deletes),
            )
        for file_object in pending_deletes:
            try:
                logger.debug(
                    "Post-commit deleting attachment file: %s",
                    getattr(file_object, "path", file_object),
                )
                await file_object.delete_async()
            except FileNotFoundError:
                # Accept already-deleted files (listener/backends may have deleted first).
                pass
            except Exception:
                logger.exception(
                    "Post-commit attachment cleanup failed for %s",
                    getattr(file_object, "path", file_object),
                )
    except IntegrityError as exc:
        session_info.pop("_lp_pending_file_deletes", None)
        raise ClientException(
            status_code=HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception:
        session_info.pop("_lp_pending_file_deletes", None)
        raise


toolbar_config = LitestarDebugToolbarConfig(
    enabled=True,
    extra_panels=["debug_toolbar.extras.advanced_alchemy.SQLAlchemyPanel"],
)


def read_yaml_config(file_path: str) -> dict:
    if not os.path.exists(file_path):
        logger.warning(
            f"Configuration file '{file_path}' not found. Using empty config."
        )
        return {}
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


@get("/favicon.ico", status_code=HTTP_204_NO_CONTENT, sync_to_thread=False)
def handle_favicon() -> None:
    return None


def init_app(lp_prefix: str = "/") -> Litestar:

    from litestar_pulse.views.components import user_menu

    # load YAML config.yaml and secret.yaml
    config = read_yaml_config("config.yaml")
    general_config.update(config)
    secret = read_yaml_config("secret.yaml")
    general_config.update(secret)

    init_filestorage()

    static_route_handler = create_static_files_router(
        path="/static/",
        directories=resources_to_paths(
            [
                "assets",
                "litestar_pulse:assets",
            ]
        ),
    )

    route_handlers = [handle_favicon, static_route_handler]
    route_handlers.extend(get_lp_controllers(lp_prefix))

    # dbc = DBConfig()
    # dbplugin = SQLAlchemyInitPlugin(
    #     config=SQLAlchemyAsyncConfig(engine_instance=dbc.engine)
    # )
    # session_factory = dbc.session_factory
    dbplugin = SQLAlchemyPlugin(config=alchemy_config)
    session_factory = alchemy_config.session_maker

    async def preload_enumkeys() -> None:
        # async with session_factory() as session:
        async with alchemy_config.get_session() as session:
            await EnumKeyRegistry.load_all(session)

    flash_plugin = FlashPlugin(config=flash_config)

    debugger = SelectiveDebugger(
        ipdb,
        # set exceptions that need to be excluded from triggering the debugger
        excluded_exceptions=(NotFoundException, NotAuthorizedException),
    )

    plugins = [
        dbplugin,
        flash_plugin,
    ]

    # when run in debug mode, use the following exception handlers
    if os.getenv("LITESTAR_DEBUG", "false").lower() in ("1", "true", "yes"):
        logger.info(
            "WARNING: DEBUG MODE IS ENABLED. This should NOT be used in production!"
        )
        plugins.append(DebugToolbarPlugin(toolbar_config))
        exception_handlers = {
            NotFoundException: handle_not_found,
            NotAuthorizedException: auth_exception_handler,
            Exception: mako_html_exception_handler,
        }
    else:
        exception_handlers = {
            NotFoundException: handle_not_found,
            NotAuthorizedException: auth_exception_handler,
        }

    # when run in PDB mode, use the following debugger
    if os.getenv("LITESTAR_PDB", "false").lower() in ("1", "true", "yes"):
        logger.info(
            "WARNING: PDB on exception is ENABLED. This should NOT be used in production!"
        )
        pdb_on_exception = True
    else:
        pdb_on_exception = False

    def add_helper_context(kwargs: dict) -> None:
        kwargs["user_menu"] = user_menu

    context_injector(add_helper_context)

    return Litestar(
        route_handlers=route_handlers,
        dependencies={"transaction": provide_transaction},
        middleware=[
            DefineMiddleware(HandlerContextMiddleware),
            session_config.middleware,
        ],
        stores={"sessions": FileStore(path=Path("session_data"))},
        on_app_init=[session_auth.on_app_init],
        on_startup=[preload_enumkeys],
        debugger_module=debugger,
        pdb_on_exception=pdb_on_exception,
        logging_config=logging_config,
        template_config=template_config,
        plugins=plugins,
        exception_handlers=exception_handlers,
    )


# EOF
