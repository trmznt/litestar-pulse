# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from typing import Any
from uuid import UUID
from enum import Enum

from sqlalchemy.orm import object_session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from markupsafe import Markup, escape

from litestar import Response, Request, get
from litestar.response import Redirect

from ..lib.template import Template
from ..lib.validators import Validator
from ..lib.formbuilder import ParseFormError, TimeStampError
from .baseview import LPBaseView

from ..lib import validators as v
from ..lib import coretags as t
from ..lib import compositetags as ct
from ..lib import forminputs as f
from ..lib import formbuilder as fb


def form_submit_bar(create: bool = False) -> t.Tag:
    if create:
        return ct.custom_submit_bar(
            ("Add", "save"), ("Add and continue editing", "save_edit")
        ).set_offset(2)
    return ct.custom_submit_bar(
        ("Save", "save"), ("Save and continue editing", "save_edit")
    ).set_offset(2)


class ModelForm:
    """
    Base class for model forms
    """

    model_type: Any

    def __init_subclass__(cls, **kwargs) -> None:
        """perform subclass-specific initialization here"""
        super().__init_subclass__(**kwargs)

    def __init__(self, obj: Any = None) -> None:
        self.obj = obj
        # if obj is not None:
        #    for field_name in self.__fields__:
        #        getattr(self, field_name).set_owner_instance(self)

    def set_fields(self, obj: Any = None) -> None:
        """
        Set the form fields based on the given object
        """
        pass

    def validate(self, obj: Any, data: dict[str, Any]) -> None:
        """
        Validate the form data based on the obj
        """
        error_lists = []

        for field_name in self.__fields__:
            if not hasattr(self, field_name):
                continue
            field_validator: Validator = getattr(self, field_name)
            value = data.get(field_name, None)
            result, err_msg = field_validator.validate(value, obj=obj)
            if not result:
                error_lists.append((f"Invalid {field_name}: {err_msg}", field_name))

        if any(error_lists):
            raise ParseFormError(error_lists)

    async def update(
        self, obj: Any, data: dict[str, Any], dbsession: AsyncSession
    ) -> None:
        """
        Update the object with the form data, this assume that the data has been validated
        """

        if object_session(obj) is None:
            raise ValueError("Object is not attached to a session")

        for field_name in self.__fields__:
            print("processing field:", field_name)
            if not hasattr(self, field_name):
                continue
            if field_name not in data:
                # field_name is not updated in the data
                continue
            field_validator: Validator = getattr(self, field_name)
            value = data.get(field_name)
            transformed_value = field_validator.transform(value)
            print("updating field:", field_name, "with value:", transformed_value)
            setattr(obj, field_name, transformed_value)

        # get database session of the object and flush to save changes

        await dbsession.flush()

    async def validate_and_update(
        self, data: dict[str, Any], dbsession: AsyncSession
    ) -> None:
        """
        Validate and update the object with the form data
        """
        self.validate(self.obj, data)
        await self.update(self.obj, data, dbsession)


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
        """
        if self.model_type is None:
            raise NotImplementedError("model_type must be set in derived class")

        repo = self.get_repository()
        options = self.augment_repo_options(for_listing=False)

        if dbid is not None:
            return await repo.get_one_or_none(id=dbid, **options)
        if uuid is not None:
            return await repo.get_one_or_none(uuid=uuid, **options)
        return None

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

        if instance is None:
            return dict(html="Instance not found", __status_code__=404)

        form = self.model_form(instance)

        return await form.html_form(
            request=self.req,
            readonly=True,
            editable=True,
            controller=self,
        )

        return self.set_layout(
            main_panel=self.main_panel(instance),
        )

        #

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
                    await form.validate_and_update(
                        data, self.dbt, check_timestamp=False
                    )

                except fb.ParseFormError as e:
                    await nested.rollback()
                    errors = e.error_list

            if any(errors):
                # re-show he form with errors

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
                await form.validate_and_update(data, self.dbt)

            except ParseFormError as e:
                await nested.rollback()
                # need to show the form with errors but exit the exception context
                errors = e.error_list

            except TimeStampError as e:
                await nested.rollback()
                errors = [(str(e), "stamp")]

                return Template(
                    template_name=self.form_template_file,
                    context={
                        "errors": errors,
                        "title": Markup("Editing ") + self.get_model_title(as_url=True),
                    },
                )

        if any(errors):
            # re-show he form with errors
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


# EOF
