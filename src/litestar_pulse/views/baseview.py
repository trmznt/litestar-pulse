# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from os import path
from uuid import UUID
import json

from markupsafe import Markup, escape

from sqlalchemy.ext.asyncio import AsyncSession

from litestar import Controller, Request, Response, get, post, patch, delete, MediaType
from litestar.response import Redirect, File
from litestar.handlers import HTTPRouteHandler
from litestar.status_codes import HTTP_303_SEE_OTHER
from litestar.handlers.base import BaseRouteHandler
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException

from litestar_pulse.config.app import logger
from litestar_pulse.db import set_handler
from litestar_pulse.db.handler import handler_factory
from litestar_pulse.lib.template import Template
from litestar_pulse.lib import roles as r
from litestar_pulse.lib.fileupload import FileUploadProxy

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tagato import tags as t


# TODO:
# [x] add security using litestar guards
# [x] add authentication using litestar authentication
# [x] add authorization using litestar authorization
# [x] add templating support using mako
# - add form handling support
# - add CSRF protection
# - add create, edit, update, delete (and delete confirmation popup) views
# - add file upload support
# - add pagination support for index view
# - add search support for index view
# - add sorting support for index view
# - add filtering support for index view
# - add better error handling
# [x] add logging support


class LPController(Controller):

    managing_roles = {r.SYSADM}
    modifying_roles = {r.SYSADM, r.DATAADM}
    viewing_roles = {r.DATAVIEW}

    @classmethod
    async def get_this_controller(cls, handler: BaseRouteHandler) -> LPController:
        # Locate the LPController-derived instance that defines viewing_roles.
        controller: LPController | None = getattr(handler.fn, "__self__", None)

        if controller is None or not isinstance(controller, LPController):
            current_owner: Any | None = handler.owner
            depth = 0
            while current_owner and depth < 10:
                if isinstance(current_owner, LPController):
                    controller = current_owner
                    break
                current_owner = getattr(current_owner, "owner", None)
                depth += 1

        return controller or cls

    @classmethod
    async def managing_role_guard(
        cls, connection: ASGIConnection, handler: BaseRouteHandler
    ) -> None:
        controller: LPController = await cls.get_this_controller(handler)
        managing_role = (
            controller.model_type.__managing_roles__
            if controller and hasattr(controller, "model_type")
            else controller.managing_roles
        )

        logger.info(
            f"guard checking managing role {managing_role} for {cls.__class__.__name__}"
        )

        if hasattr(controller, "model_type") and controller.model_type is not None:
            if not controller.model_type.can_manage(
                connection.user.roles if hasattr(connection.user, "roles") else set()
            ):
                raise NotAuthorizedException(
                    "User does not have required managing roles."
                )
        else:
            # Fallback to the controller's managing_roles if no model_type is defined
            if not controller.managing_roles & (
                connection.user.roles if hasattr(connection.user, "roles") else set()
            ):
                raise NotAuthorizedException(
                    "User does not have required managing roles."
                )

        # if required_role and connection.user.role != required_role:
        #    raise NotAuthorizedException(f"Missing required role: {required_role}")

    @classmethod
    async def viewing_role_guard(
        cls, connection: ASGIConnection, handler: BaseRouteHandler
    ) -> None:
        # Locate the LPController-derived instance that defines viewing_roles.

        controller: LPController = await cls.get_this_controller(handler)
        viewing_roles = (
            controller.model_type.__viewing_roles__
            if controller and hasattr(controller, "model_type")
            else controller.viewing_roles
        )

        logger.info(
            "guard checking viewing role %s for user with roles %s in %s",
            viewing_roles,
            connection.user.roles if hasattr(connection.user, "roles") else None,
            controller,
        )

        if hasattr(controller, "model_type") and controller.model_type is not None:
            if not controller.model_type.can_view(
                connection.user.roles if hasattr(connection.user, "roles") else set()
            ):
                raise NotAuthorizedException(
                    "User does not have required viewing roles."
                )
        else:
            # Fallback to the controller's viewing_roles if no model_type is defined
            if not controller.viewing_roles & (
                connection.user.roles if hasattr(connection.user, "roles") else set()
            ):
                raise NotAuthorizedException(
                    "User does not have required viewing roles."
                )

        # if required_role and connection.user.role != required_role:
        #    raise NotAuthorizedException(f"Missing required role: {required_role}")

    def get_route_handlers(self):
        # Retrieve the handlers as Litestar has prepared them
        handlers = super().get_route_handlers()
        class_name = self.get_controller_handler_name()

        for handler in handlers:
            if isinstance(handler, HTTPRouteHandler):
                # 1. Determine the base name (manually set name or function name)
                # handler.name holds the manual name if provided, else it's None or the fn name
                base_name = handler.name or handler.fn.__name__

                # 2. Re-assign the name using the required pattern
                handler.name = f"{class_name}-{base_name}"
                if False:
                    logger.info(
                        "Registered handler %s with paths %s",
                        handler.name,
                        handler.paths or [self.path or "/"],
                    )

        return handlers

    def init_view(
        self, request: Request, db_session: AsyncSession, transaction: AsyncSession
    ) -> None:
        """
        Initialize the view
        """
        # current request
        self.req: Request = request

        # database session
        self.dbs: AsyncSession = db_session

        # database transaction
        self.dbt: AsyncSession = transaction

        # database handler
        self.dbh: Any = handler_factory(self.dbt)
        set_handler(self.dbh)

    def get_controller_handler_name(self) -> str:
        return self.__class__.__name__.lower().removesuffix("view")


class LPBaseView(LPController):
    """
    BaseView is Controller-derived class that return html response
    """

    plain_template_file = "lp/generics/page.mako"
    form_template_file = "lp/generics/formpage.mako"

    @staticmethod
    def normalize_form_data(form_data: Any, request: Request) -> dict[str, Any]:
        """Convert request form data to dict while preserving repeated keys as lists."""

        if hasattr(form_data, "multi_items"):
            data: dict[str, Any] = {}
            for key, value in form_data.multi_items():
                if key in data:
                    existing = data[key]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        data[key] = [existing, value]
                else:
                    data[key] = value
        elif hasattr(form_data, "items"):
            data = dict(form_data.items())
        else:
            data = dict(form_data)

        # for values with keys ending with ":json:", try to parse them as JSON
        for key, value in data.items():
            if isinstance(value, str) and key.endswith(":json:"):
                try:
                    data[key] = json.loads(value)
                except json.JSONDecodeError:
                    # If parsing fails, keep the original string value
                    pass

        # for keys having "NAME-:fileupload:json", parse the dictionary
        # to list of FileUploadProxy objects, and store the list to
        # NAME attribute.
        for key, value in data.items():
            if key.endswith("-:fileupload:json:"):
                try:
                    field_name = key.removesuffix("-:fileupload:json:")
                    file_uploads = []
                    if isinstance(value, str):
                        value = json.loads(value)
                    if isinstance(value, list):
                        for item in value:
                            if (
                                isinstance(item, dict)
                                and "id" in item
                                and "name" in item
                            ):
                                file_uploads.append(
                                    FileUploadProxy(
                                        upload_id=item["id"],
                                        filename=item["name"],
                                        request=request,
                                        selected=bool(item.get("selected", True)),
                                        description=str(
                                            item.get("description", "") or ""
                                        ),
                                        category=str(item.get("category", "") or ""),
                                    )
                                )
                    data[field_name] = file_uploads

                except Exception as e:
                    raise e

        return data

    async def index(self) -> dict[str, t.Tag | str]:
        """
        Render index page
        """
        raise NotImplementedError

    @get(name="index", guards=[LPController.viewing_role_guard])
    async def index_html(
        self, request: Request, db_session: AsyncSession, transaction: AsyncSession
    ) -> Template:
        """
        Render index page
        """
        request.logger.info("Rendering index page for %s", self.__class__.__name__)
        self.init_view(request, db_session, transaction)
        ctx = await self.index()
        ctx.setdefault("title", f"List of {self.__class__.__name__}")
        return Template(template_name=self.plain_template_file, context=ctx)

    async def view(self, dbid: int | None = None, uuid: str | None = None) -> Any:
        """
        Render view by ID or UUID page
        """
        raise NotImplementedError

    @get(
        path="/uuid/{uuid:uuid}",
        name="view-uuid",
        guards=[LPController.viewing_role_guard],
    )
    async def view_uuid_html(
        self,
        uuid: UUID,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Template:
        """
        Render view by UUID page
        """
        request.logger.info(
            "Rendering view-uuid page for %s with uuid %s",
            self.__class__.__name__,
            uuid,
        )
        self.init_view(request, db_session, transaction)
        ctx = await self.view(uuid=uuid)
        ctx.setdefault("title", Markup("Viewing ") + self.get_model_title(as_url=True))
        return Template(template_name=self.form_template_file, context=ctx)

    @get(path="/{dbid:int}", name="view-id", guards=[LPController.viewing_role_guard])
    async def view_id_html(
        self,
        dbid: int,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Template:
        """
        Render view by ID page
        """
        request.logger.info(
            "Rendering view-id page for %s with dbid %d", self.__class__.__name__, dbid
        )
        self.init_view(request, db_session, transaction)
        ctx = await self.view(dbid=dbid)
        ctx.setdefault("title", Markup("Viewing ") + self.get_model_title(as_url=True))
        return Template(template_name=self.form_template_file, context=ctx)

    @get(
        path="/{dbid:int}/edit", name="edit", guards=[LPController.managing_role_guard]
    )
    async def edit_id_html(
        self,
        dbid: int,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Template:
        """
        Render edit by ID page
        """
        request.logger.info(
            "Rendering edit-id page for %s with dbid %d", self.__class__.__name__, dbid
        )
        self.init_view(request, db_session, transaction)
        ctx = await self.edit(dbid=dbid)
        ctx.setdefault("title", Markup("Editing ") + self.get_model_title(as_url=True))
        return Template(template_name=self.form_template_file, context=ctx)

    async def edit(self, dbid: int | None = None) -> Any:
        """
        Render edit by ID page
        """
        raise NotImplementedError

    @post(path="/create", name="create")
    async def create_html(
        self,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Response[str]:
        """
        Render create page
        """
        request.logger.info("Rendering create page for %s", self.__class__.__name__)
        self.init_view(request, db_session, transaction)
        content = await self.create()
        return Response(content=str(content), media_type="text/html")

    async def create(self) -> Any:
        """
        Render create page
        """
        raise NotImplementedError

    @post(
        path="/{dbid:int}/update",
        name="update",
        guards=[LPController.managing_role_guard],
    )
    async def update_id_html(
        self,
        dbid: int,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Response[str] | Template:
        """
        Render update by ID page
        """
        request.logger.info(
            "Rendering update-id page for %s with dbid %d",
            self.__class__.__name__,
            dbid,
        )
        self.init_view(request, db_session, transaction)
        form_data = await request.form()
        data = self.normalize_form_data(form_data, request)

        response = await self.update(dbid=dbid, data=data)

        # after update, redirect to view page
        return response

    async def update(self, dbid: int | None, data: dict[str, Any]) -> Any:
        """
        update by dbid using data as dictionary to update,
        should return html content
        """
        raise NotImplementedError

    @delete(
        path="/{dbid:int}/delete",
        name="delete",
        status_code=HTTP_303_SEE_OTHER,
        guards=[LPController.managing_role_guard],
    )
    async def delete_id_html(
        self,
        dbid: int,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Redirect:
        """
        Render delete by ID page
        """
        request.logger.info(
            "Rendering delete-id page for %s with dbid %d",
            self.__class__.__name__,
            dbid,
        )
        self.init_view(request, db_session, transaction)
        await self.delete(dbid=dbid)
        redirect_url = request.url_for(
            f"{self.__class__.__name__.lower().removesuffix('view')}-index"
        )
        return Redirect(path=redirect_url)

    async def delete(self, dbid: int | None = None) -> Response[str] | Template:
        """
        Render delete by ID page
        """
        raise NotImplementedError

    @post(
        path="/action",
        name="action",
        status_code=HTTP_303_SEE_OTHER,
        guards=[LPController.managing_role_guard],
    )
    async def action_html(
        self,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Response[str] | Template:
        """
        Render delete confirmation page
        """
        request.logger.info(
            "Rendering delete-confirmation page for %s", self.__class__.__name__
        )
        self.init_view(request, db_session, transaction)
        form_data = await request.form()
        return await self.action(form_data)
        content = await self.action(form_data)
        return Response(content=str(content), media_type="text/html")
        return Template(
            template_name=self.plain_template_file,
            context={
                "content": content,
                "title": f"Delete Confirmation - {self.__class__.__name__}",
            },
        )

    async def action(self, data: dict[str, Any]) -> Any:
        """
        Handle action request
        """
        raise NotImplementedError

    @post(path="/delete", name="multiple-delete", status_code=HTTP_303_SEE_OTHER)
    async def delete_html(
        self,
        request: Request,
        data: dict[str, Any],
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Redirect:
        """
        Render API delete by ID page
        """
        dbids = data.get("dbids", [])
        request.logger.info(
            "Rendering api-delete-id page for %s with dbid %s",
            self.__class__.__name__,
            dbids,
        )
        self.init_view(request, db_session, transaction)
        await self.api_delete(dbid=dbids)
        redirect_url = request.url_for(
            f"{self.__class__.__name__.lower().removesuffix('view')}-index"
        )
        return Redirect(path=redirect_url)

    @get(path="/lookup", name="lookup")
    async def lookup_html(
        self,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Template:
        """
        Render lookup page
        """
        request.logger.info("Rendering lookup page for %s", self.__class__.__name__)
        self.init_view(request, db_session, transaction)
        content = await self.lookup()
        return Template(
            template_name=self.plain_template_file,
            context={
                "content": content,
                "title": f"Lookup - {self.__class__.__name__}",
            },
        )

    async def lookup(self) -> Any:
        """
        Render lookup page
        """
        raise NotImplementedError

    @get(
        path="/{dbid:int}/attachment",
        name="attachment",
        guards=[LPController.viewing_role_guard],
    )
    async def attachment_html(
        self,
        dbid: int,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> File:
        """
        Render attachment page
        """
        request.logger.info(
            "Rendering attachment page for %s with dbid %d",
            self.__class__.__name__,
            dbid,
        )
        self.init_view(request, db_session, transaction)
        return await self.attachment(dbid=dbid)

    async def attachment(self, dbid: int | None = None) -> File:
        """
        Render attachment page
        """
        raise NotImplementedError

    @get(
        path="/{dbid:int}/files/{fname:str}",
        name="files",
        guards=[LPController.viewing_role_guard],
    )
    async def files_html(
        self,
        dbid: int,
        fname: str,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> File:
        """
        Render file page
        """
        request.logger.info(
            "Rendering file page for %s with dbid %d",
            self.__class__.__name__,
            dbid,
        )
        self.init_view(request, db_session, transaction)
        return await self.files(dbid=dbid, fname=fname)

    async def files(self, dbid: int | None = None, fname: str | None = None) -> File:
        raise NotImplementedError


# EOF
