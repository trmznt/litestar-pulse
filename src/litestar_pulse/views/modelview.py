# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import uuid

from litestar.exceptions import HTTPException

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import pathlib
from typing import Any
from uuid import UUID
from enum import Enum

import re

from sqlalchemy.orm import object_session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from markupsafe import Markup, escape
from tagato import tags as t, formfields as f

from litestar import Response, Request, get
from litestar.response import File, Redirect
from litestar.plugins.flash import flash
from litestar.exceptions import NotFoundException, NotAuthorizedException

from ..lib.template import Template
from ..lib.validators import Validator
from ..lib.formbuilder import ParseFormError, TimeStampError
from ..lib.popup import modal_delete
from ..lib import validators as v
from ..lib import compositetags as ct
from ..lib import formbuilder as fb
from .baseview import LPBaseView


def form_submit_bar(create: bool = False) -> t.Tag:
    if create:
        return ct.custom_submit_bar(
            ("Add", "save"), ("Add and continue editing", "save_edit")
        ).set_offset(2)
    return ct.custom_submit_bar(
        ("Save", "save"), ("Save and continue editing", "save_edit")
    ).set_offset(2)


class LPModelView(LPBaseView):
    """
    BaseView for model-based views

    layout for view method
    +---------------------------+--------------------------+
    |                           |                          |
    |     left_top_panel        |   right_top_panel        |
    |                           |                          |
    +------------------------------------------------------+
    |                                                      |
    |                    top_panel                         |
    |                                                      |
    +------------------------------------------------------+
    |                                                      |
    |                     main panel                       |
    |                                                      |
    +------------------------------------------------------+
    |                                                      |
    |                    bottom_panel                      |
    |                                                      |
    +---------------------------+--------------------------+
    |                           |                          |
    |     left_bottom_panel     |   right_bottom_panel     |
    |                           |                          |
    +---------------------------+--------------------------+

    main_panel may contain:
    - instance table for listing multiple instances
    - instance form for viewing/editing a single instance
    - instance detail for viewing a single instance without form

    bottom_panel may contain:
    - additional information or actions related to the instance(s) in the main panel,
      such as related objects or related multiple attributes. For example, user view
      should have groups where the user belongs to in the bottom panel

    edit method should only show main_panel

    """

    model_type: Any = None  # to be set in derived class
    order_by: Any = None  # to be set in derived class
    model_form: Any = None  # to be set in derived class

    model_title: str | None = None

    # override the following methods

    def generate_instance_table(self, instances: list[Any]) -> tuple[t.htmltag, str]:
        """
        Generate the instance table for the given instances
        """
        raise NotImplementedError(
            "generate_instance_table must be implemented in derived class"
        )

    def augment_repo_options(self, for_listing: bool = False) -> dict[str, Any]:
        """
        Augment repository options before execution.
        for_listing indicates if the operation is for listing multiple instances.
        """
        return {
            "load": [joinedload(self.model_type.updated_by)],
        }

    async def additional_action(self, data: dict[str, Any]) -> Any:
        """
        Handle additional actions that are not covered by the default implementations.
        This method can be overridden in derived classes to handle custom actions.
        """
        raise NotImplementedError(
            "_method argument is not recognized: %s" % data.get("_method", "None")
        )

    def get_attachment_url(
        self,
        instance: Any,
    ) -> t.Tag | None:
        """
        Get the file URL for the given instance and field, if any.
        This method can be overridden in derived classes to provide the correct URL for the file field.
        By default, it returns None, which means no file URL will be provided to the FileUploadField.
        """
        file_object = getattr(instance, "attachment", None)
        if file_object:
            return t.fragment[
                t.a(
                    href=self.req.url_for(
                        f"{self.model_type.__name__.lower()}-attachment",
                        dbid=instance.id,
                    ),
                    target="_blank",
                )[
                    (
                        file_object.metadata.get("filename")
                        if file_object.metadata
                        else "No original filename"
                    )
                ],
                " ",
                file_object.size,
            ]
        return None

    async def attachment(self, dbid: int | None = None) -> File:
        """
        Render attachment page
        """
        instance = await self.get_model_instance(dbid=dbid)
        file_object = getattr(instance, "attachment", None)
        if file_object:
            path = pathlib.Path(file_object.backend.prefix) / file_object.path
            return File(
                path=path,
                filename=file_object.metadata.get("filename"),
                content_disposition_type="inline",
            )

    def get_files_url(self, filekey: str, instance: Any) -> str:
        """
        Get the URL for the given file key, which can be used by
        the FileUploadField to upload files.
        This method should be overridden by the subclass to provide
        the correct implementation of generating the file URL based
        on the file key if it differs from the default implementation.
        The file key can be used to identify the file in the backend
        storage and map it to the corresponding model instance and field.
        """
        return self.req.url_for(
            f"{self.model_type.__name__.lower()}-files",
            dbid=getattr(instance, "id", None),
            fname=filekey.rsplit("/", 1)[1] if "/" in filekey else filekey,
        )

    async def files(self, dbid: int | None = None, fname: str | None = None) -> File:
        """Render file page
        - dbid and fname can be used to locate the file to be rendered
        - the file can be located in the filesystem or in the database as blob
        - the file can be rendered using File response with appropriate media type
        - if the file is not found, return 404 response
        - if the user is not authorized to access the file, return 403 response
        - if there is an error while processing the request, return 500 response
        - this method should be overridden by the subclass to provide the correct
          implementation of locating and rendering the file if differing from
          default implementation
        - this method can also be used to perform any necessary authorization checks
          before rendering the file
        - this method can also be used to perform any necessary logging before
          rendering the file
        - this method should return a File response with appropriate media type
          if the file is found and accessible, or raise an appropriate exception
          if not
        """

        instance = await self.get_model_instance_with_check(dbid=dbid)
        fileobjectlist = getattr(instance, "files", None)
        if fileobjectlist is None:
            raise NotFoundException("No files associated with this instance")
        file_object = next((f for f in fileobjectlist if f.path.endswith(fname)), None)
        if not file_object:
            raise NotFoundException("File not found")

        path = pathlib.Path(file_object.backend.prefix) / file_object.path
        return File(
            path=path,
            filename=file_object.metadata.get("filename"),
            content_disposition_type="inline",
        )

        # perform authorization check if necessary

    # main methods

    def get_repository(self) -> Any:
        return self.dbh.get_repository(self.model_type)

    def _normalize_order_by(self, order_by: Any) -> Any:
        if order_by is None:
            return None
        if isinstance(order_by, list):
            return order_by
        if isinstance(order_by, tuple):
            if len(order_by) == 2 and isinstance(order_by[1], bool):
                return [order_by]
            if len(order_by) > 0 and isinstance(order_by[0], tuple):
                return list(order_by)
        return [(order_by, False)]

    async def get_all_instances(self) -> list[Any]:
        """
        Retrieve all model instances
        """
        repo = self.get_repository()
        options = self.augment_repo_options(for_listing=True)
        if self.order_by is not None:
            options["order_by"] = self._normalize_order_by(self.order_by)
        return await repo.list(**options)

    async def get_model_instance(
        self, dbid: int | None = None, uuid: UUID | None = None
    ) -> Any:
        """
        Retrieve model instance by ID or UUID
        FIXME: implement proper authorization check based on the instance and the user
        FIXME: implement proper error handling and logging
        """
        if self.model_type is None:
            raise NotImplementedError("model_type must be set in derived class")

        repo = self.get_repository()
        options = self.augment_repo_options(for_listing=False)

        if dbid is not None:
            instance = await repo.get_one_or_none(id=dbid, **options)
        if uuid is not None:
            instance = await repo.get_one_or_none(uuid=uuid, **options)

        return instance

    async def get_model_instance_with_check(
        self, dbid: int | None = None, uuid: UUID | None = None
    ) -> Any:
        """
        Retrieve model instance by ID or UUID with existence and authorization check
        """
        instance = await self.get_model_instance(dbid=dbid, uuid=uuid)
        if instance is None:
            raise NotFoundException("Instance not found")

        # FIXME: implement proper authorization check based on the instance and the user
        return instance

    async def index(
        self, data: dict[str, Any] | None = None
    ) -> dict[str, t.htmltag | str]:
        """
        Render the user domain list page
        """

        instances = await self.get_all_instances()

        html, code = self.generate_instance_table(instances)
        return dict(html=html, code=code)

    async def view(
        self, dbid: int | None = None, uuid: str | None = None
    ) -> dict[str, t.htmltag | str]:
        """
        Render the user domain detail page by ID or UUID
        """

        instance = await self.get_model_instance(dbid=dbid, uuid=uuid)
        if hasattr(instance, "attachment"):
            print("attachment:", instance.attachment)

        if instance is None:
            return dict(html="Instance not found", __status_code__=404)

        form = self.model_form(instance)

        ctx = self.compose_layout(
            main_panel=await self.get_main_panel(instance),
            top_panel=await self.get_top_panel(instance),
            left_top_panel=await self.get_left_top_panel(instance),
            right_top_panel=await self.get_right_top_panel(instance),
            left_bottom_panel=await self.get_left_bottom_panel(instance),
            right_bottom_panel=await self.get_right_bottom_panel(instance),
            bottom_panel=await self.get_bottom_panel(instance),
        )

        return ctx

    async def edit(
        self, dbid: int | None = None, uuid: str | None = None
    ) -> dict[str, t.htmltag | str]:
        """
        Render the user domain edit page by ID or UUID
        """
        if dbid is not None and dbid == 0:
            # create new instance
            instance = self.model_type()
            instance.id = 0
            form = self.model_form(instance)
            return await form.html_form(
                request=self.req,
                readonly=False,
                editable=True,
                controller=self,
            )

        instance = await self.get_model_instance(dbid=dbid, uuid=uuid)

        if instance is None:
            return dict(
                html=t.div()[
                    t.h2()["User Domain not found"],
                    t.p()["The requested user domain with ID or UUID does not exist."],
                ],
                __status_code__=404,
            )

        form = self.model_form(instance)

        return await form.html_form(
            request=self.req,
            readonly=False,
            editable=True,
            controller=self,
        )

    async def update(
        self, dbid: int | None = None, data: dict[str, Any] = {}
    ) -> Response[str]:
        """
        Handle the user domain update by ID or UUID
        """

        # !!! raise here if to inspect normalized data
        # raise RuntimeError(f"normalized data: {data}")

        if dbid is not None and dbid == 0:
            # create new instance
            instance = self.model_type()

            # check with validators
            form = self.model_form(instance, data)

            errors = []
            async with self.dbt.begin_nested() as nested:
                try:
                    # validate and update to database
                    self.dbt.add(instance)
                    await form.transform_and_update(
                        data, self.dbh, check_timestamp=False
                    )

                except fb.ParseFormError as e:
                    await nested.rollback()
                    errors = e.error_list

            if any(errors):
                # re-show the form with errors

                ctx = await form.html_form(
                    request=self.req,
                    readonly=False,
                    editable=True,
                    controller=self,
                    errors=errors,
                )
                ctx.setdefault(
                    "title", Markup("Editing ") + self.get_model_title(as_url=True)
                )
                return Template(template_name=self.form_template_file, context=ctx)

            return Redirect(
                path=self.req.url_for(
                    self.get_controller_handler_name() + "-view-id", dbid=instance.id
                )
            )

        instance = await self.get_model_instance(dbid=dbid)

        if instance is None:
            raise RuntimeError("Instance does not exist or has been deleted")

        # check with validators
        form = self.model_form(instance)

        errors = []
        async with self.dbt.begin_nested() as nested:
            try:
                # validate and update to database
                await form.transform_and_update(data, self.dbh, check_timestamp=True)

            except ParseFormError as e:
                await nested.rollback()
                # need to show the form with errors but exit the exception context
                errors = e.error_list

            except TimeStampError as e:
                await nested.rollback()
                errors = [(str(e), "stamp")]

                return Template(
                    template_name="lp/generics/errorpage.mako",
                    context={
                        "errors": errors,
                        "title": Markup("Editing ") + self.get_model_title(as_url=True),
                    },
                )

        if any(errors):
            # re-show the form with errors
            form = self.model_form(await self.get_model_instance(dbid=dbid), data)
            ctx = await form.html_form(
                request=self.req,
                readonly=False,
                editable=True,
                controller=self,
                errors=errors,
            )
            ctx.setdefault(
                "title", Markup("Editing ") + self.get_model_title(as_url=True)
            )
            return Template(template_name=self.form_template_file, context=ctx)

        # below determines the next URL based on the submit button
        next_url = (
            self.get_controller_handler_name() + "-edit"
            if data["_method"] == "save_edit"
            else self.get_controller_handler_name() + "-view-id"
        )
        return Redirect(path=self.req.url_for(next_url, dbid=dbid))

    async def action(self, data: dict[str, Any]) -> Any:
        """
        Handle the delete confirmation,
        """
        dbids = data.getall(f"{self.model_type.__name__.lower()}-ids", [])

        match data.get("_method", None):

            case "delete-confirmation":

                return modal_delete(
                    title=f"Confirm Deletion of {len(dbids)} {self.get_model_title()}(s)",
                    content=t.fragment()[
                        t.p()[
                            "Are you sure you want to delete the selected %s? This action cannot be undone."
                            % self.get_model_title()
                        ],
                        t.p()[t.strong()[f"IDs to be deleted: {', '.join(dbids)}"]],
                    ],
                    request=self.req,
                )

            case "delete-confirmed":

                await self.dbh.get_repository(self.model_type).delete_many(dbids)
                flash(
                    self.req,
                    "%d %s(s) deleted successfully!"
                    % (len(dbids), self.get_model_title()),
                    category="success",
                )
                return Redirect(
                    path=self.req.url_for(self.get_controller_handler_name() + "-index")
                )

        return await self.additional_action(data)

    # layoutting

    def get_model_title(self, as_url: bool = False) -> str | t.htmltag:
        """
        Get the model title for display purposes
        """
        title = self.model_title
        if title is None:
            title = self.model_type.__name__
        if title is None:
            title = self.__class__.__name__.removesuffix("View")

        if not as_url:
            return title

        return t.a(
            href=self.req.url_for(self.get_controller_handler_name() + "-index"),
            class_="navbar-brand",
        )[escape(title)]

    def compose_layout(
        self,
        main_panel: dict[str, t.htmltag | str] | None = None,
        top_panel: dict[str, t.htmltag | str] | None = None,
        left_top_panel: dict[str, t.htmltag | str] | None = None,
        right_top_panel: dict[str, t.htmltag | str] | None = None,
        left_bottom_panel: dict[str, t.htmltag | str] | None = None,
        right_bottom_panel: dict[str, t.htmltag | str] | None = None,
        bottom_panel: dict[str, t.htmltag | str] | None = None,
    ) -> dict[str, t.htmltag | str]:
        """
        Compose the layout for the view.
        Each of dictionary parameters is expected to have an "html" key with the HTML content,
        and optionally a "jscode", "pyscode" and "scriptlinks" key for additional
        JavaScript code, pyscript code and script links to be included in the page.
        """

        jscode: list[str] = []
        pyscode: list[str] = []
        scriptlinks: list[str] = []

        fragments = t.fragment()
        if top_panel:
            fragments.add(t.div(class_="row", name="top_panel")[top_panel["html"]])

        if left_top_panel or right_top_panel:
            fragments.add(
                t.div(class_="row", name="left_right_top_panel")[
                    t.div(class_="col-md-6", name="left_top_panel")[
                        left_top_panel["html"] if left_top_panel else ""
                    ],
                    t.div(class_="col-md-6", name="right_top_panel")[
                        right_top_panel["html"] if right_top_panel else ""
                    ],
                ]
            )
        if main_panel:
            fragments.add(t.div(class_="row", name="main_panel")[main_panel["html"]])
        if left_bottom_panel or right_bottom_panel:
            fragments.add(
                t.br,
                t.div(class_="row", name="left_right_bottom_panel")[
                    t.div(class_="col-md-6", name="left_bottom_panel")[
                        left_bottom_panel["html"] if left_bottom_panel else ""
                    ],
                    t.div(class_="col-md-6", name="right_bottom_panel")[
                        right_bottom_panel["html"] if right_bottom_panel else ""
                    ],
                ],
            )
        if bottom_panel:
            fragments.add(
                t.hr,
                t.div(class_="row", name="bottom_panel")[bottom_panel["html"]],
            )

        # collate the additional jscode, pyscode and scriptlinks from the panels
        for panel in [
            main_panel,
            top_panel,
            left_top_panel,
            right_top_panel,
            left_bottom_panel,
            right_bottom_panel,
            bottom_panel,
        ]:
            if panel is None:
                continue
            if "javascript_code" in panel:
                jscode.append(panel["javascript_code"])
            if "jscode" in panel:
                jscode.append(panel["jscode"])
            if "pyscript_code" in panel:
                pyscode.append(panel["pyscript_code"])
            if "scriptlink_lines" in panel:
                scriptlinks.extend(panel["scriptlink_lines"])

        return dict(
            html=fragments,
            javascript_code="\n".join(jscode),
            pyscript_code="\n".join(pyscode),
            scriptlink_lines="\n".join(scriptlinks),
        )

    async def get_main_panel(self, instance: Any) -> dict[str, t.htmltag | str] | None:
        """
        Get the main panel for the given instance, by default it will show the instance detail
        """

        form = self.model_form(instance)

        return await form.html_form(
            request=self.req,
            readonly=True,
            editable=True,
            controller=self,
        )

    async def get_top_panel(self, instance: Any) -> dict[str, t.htmltag | str] | None:
        """
        Get the top panel for the given instance, by default it will show the model title
        """
        return None

    async def get_bottom_panel(
        self, instance: Any
    ) -> dict[str, t.htmltag | str] | None:
        """
        Get the bottom panel for the given instance, by default it will show nothing
        """
        return None

    async def get_left_top_panel(
        self, instance: Any
    ) -> dict[str, t.htmltag | str] | None:
        """
        Get the left top panel for the given instance, by default it will show nothing
        """
        return None

    async def get_right_top_panel(
        self, instance: Any
    ) -> dict[str, t.htmltag | str] | None:
        """
        Get the right top panel for the given instance, by default it will show nothing
        """
        return None

    async def get_left_bottom_panel(
        self, instance: Any
    ) -> dict[str, t.htmltag | str] | None:
        """
        Get the left bottom panel for the given instance, by default it will show nothing
        """
        return None

    async def get_right_bottom_panel(
        self, instance: Any
    ) -> dict[str, t.htmltag | str] | None:
        """
        Get the right bottom panel for the given instance, by default it will show nothing
        """
        return None


# ---
# utilities
# ---


def parse_indexed_form_xxx(form_data: Any, group_name: str) -> list[dict]:
    """
    Parses MultiDict keys like 'items[0][id]' into a list of dictionaries.
    """
    structured_data = {}
    # Pattern to match: items[0][id]
    pattern = re.compile(rf"{group_name}\[(\w+)\]\[(\w+)\]")

    for key, value in form_data.items():
        match = pattern.match(key)
        if match:
            index, field = match.groups()

            if index not in structured_data:
                structured_data[index] = {}

            structured_data[index][field] = value

    # Return as a list of dictionaries
    return list(structured_data.values())


# Compiled once when the module loads
INDEXED_PATTERN = re.compile(r"(\w+)\[(\w+)\]\[(\w+)\]")


def parse_indexed_form(form_data: Any) -> dict[str, list[dict]]:
    """Optimised version for multiple groups in one pass."""
    results = {}
    for key, value in form_data.items():
        match = INDEXED_PATTERN.match(key)
        if match:
            group, index, field = match.groups()
            group_list = results.setdefault(group, {})
            row = group_list.setdefault(index, {})
            row[field] = value

    # Convert inner dicts to lists
    return {g: list(rows.values()) for g, rows in results.items()}


# EOF
