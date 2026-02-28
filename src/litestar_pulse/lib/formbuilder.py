# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from typing import Any, Self
from dataclasses import dataclass
from functools import cached_property

from markupsafe import Markup, escape

from sqlalchemy.orm import object_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import exc

from litestar import Request

from . import validators as v
from . import forminputs as f
from . import coretags as t
from . import compositetags as ct

from ..db.models.enumkey import EnumKeyRegistry


class ParseFormError(ValueError):

    def __init__(self, error_list: list[(str, str)]):
        """
        Docstring for __init__

        :param error_list: list of tuples of (message, field name)
        """
        super().__init__(f"Value error(s) in {len(error_list)} field(s): {error_list}")
        self.error_list = error_list


class DatabaseUpdateError(ValueError):

    def __init__(self, message: str, input_field: InputField):
        """
        Docstring for __init__

        :param input_field: the InputField instance that caused the error
        :param message: message to be shown
        """
        super().__init__(message)
        self.input_field = input_field


class TimeStampError(ValueError):

    def __init__(self, message: str):
        """
        Docstring for __init__

        :param message: message to be shown
        """
        super().__init__(message)


@dataclass
class _InputFieldProxy:
    """
    _InputFieldProxy convert the operation to either validator or forminput
    """

    owner_instance: Any  # the instance of ModelForm
    name: str  # the name of the field
    input_field: InputField  # the InputField instance

    def get_value(self) -> Any:
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")

        if self.name in data:
            return data[self.name]
        if obj is not None:
            return getattr(obj, self.name, "") or ""
        return ""

    def validate(self, value: Any, obj: Any | None = None) -> tuple[bool, str]:
        return self.input_field.validator.validate(value, obj=obj)

    def transform(self, value: Any) -> Any:
        return self.input_field.validator.transform(value)

    @cached_property
    def form_input(self) -> f.BaseInput:
        return self.input_field.forminput(
            label=self.input_field.label,
            inputfield=self,
        )

    def opts(self, col=None, **kwargs: Any) -> f.BaseInput:
        self.form_input.opts(col=col, **kwargs)
        return self

    def __tag__(self) -> t.Tag:
        return self.form_input


class _ForeignKeyInputFieldProxy(_InputFieldProxy):

    def opts(self, option_callback=None, **kwargs: Any) -> f.BaseInput:
        if option_callback is not None:
            self.form_input.option_callback = option_callback
        self.form_input.opts(**kwargs)
        return self

    def get_value(self) -> tuple[int | None, str | None]:
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")
        if self.name in data:
            if self.input_field.nullable and data[self.name] == "":
                return (None, "")
            value = int(data[self.name])
            text = None
            if value is not None and self.input_field.foreignkey_for is not None:
                related_obj = getattr(obj, self.input_field.foreignkey_for, None)
                if related_obj is not None:
                    text = getattr(related_obj, self.input_field.text_from, "")
            return (value, text)

        if obj is not None:
            value = getattr(obj, self.name, None)
            text = ""
            if value is not None and self.input_field.foreignkey_for is not None:
                related_obj = getattr(obj, self.input_field.foreignkey_for)
                text = getattr(related_obj, self.input_field.text_from, "")
            print(f"ForeignKeyField object={obj} get_value: value={value}, text={text}")
            return (value, text)
        return (None, "")


class _EnumKeyInputFieldProxy(_InputFieldProxy):

    def get_value(self) -> tuple[int | None, str | None]:
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")
        if self.name in data:
            value = int(data[self.name])
            ekey = EnumKeyRegistry.get_by_id(None, value)
            return (value, ekey.key)
        if obj is not None:
            value = getattr(obj, self.name, None)
            if value is not None and self.input_field.foreignkey_for is not None:
                ekey = getattr(obj, self.input_field.foreignkey_for, "")
                return (value, ekey.key)
        return (None, None)

    def get_options(self) -> list[tuple[int, str]]:
        obj = getattr(self.owner_instance, "obj", None)
        if obj is None:
            raise RuntimeError("Owner instance does not have an 'obj' attribute")
        enumproxy_name = self.input_field.foreignkey_for
        if enumproxy_name is None:
            raise RuntimeError("Validator does not have 'foreignkey_for' set")
        enumproxy = getattr(obj.__class__, enumproxy_name, None)
        if enumproxy is None:
            raise RuntimeError(
                f"Object class {obj.__class__.__name__} does not have EnumKeyProxy attribute '{enumproxy_name}'"
            )
        category_key = enumproxy.category_key
        enumkey_registry = enumproxy.__registry__
        return enumkey_registry.get_all_items(category_key)


class _DBEnumKeyInputFieldProxy(_InputFieldProxy):
    """this class is for ForeignKeyField that reference EnumKey"""

    def opts(self, option_callback=None, **kwargs: Any) -> f.BaseInput:
        if option_callback is not None:
            self.form_input.option_callback = option_callback
        self.form_input.opts(**kwargs)
        return self

    def get_value(self) -> tuple[int | None, str | None]:
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")
        if self.name in data:
            value = int(data[self.name])
            text = None
            if value is not None and self.input_field.foreignkey_for is not None:
                related_obj = getattr(obj, self.input_field.foreignkey_for, None)
                if related_obj is not None:
                    text = getattr(related_obj, self.input_field.text_from, "")
            return (value, text)

        if obj is not None:
            value = getattr(obj, self.name, None)
            text = ""
            if value is not None and self.input_field.foreignkey_for is not None:
                related_obj = getattr(obj, self.input_field.foreignkey_for)
                text = getattr(related_obj, self.input_field.text_from, "")
            return (value, text)
        return (None, None)


@dataclass
class InputField:

    validator: v.Validator
    forminput: type[f.BaseInput]
    label: str | None = None

    # required when needed when creating new instance, but not necessary
    # when updating existing instance
    required: bool = False

    # if this field can be null in the database, this is used to determine
    # if empty value should be transformed to None
    # nullable: bool = False

    foreignkey_for: str | None = None
    text_from: str | None = None

    # the proxy
    proxy_class: type = _InputFieldProxy

    field_list = "__fields__"

    def __post_init__(self) -> None:
        self.validator.set_owner_instance(self)

    def __set_name__(self, owner: Any, name: str) -> None:
        self._name = name
        self._owner = owner

        if self.field_list not in owner.__dict__:
            setattr(owner, self.field_list, [])
        getattr(owner, self.field_list).append(name)
        print(f"Registered field: {name} in {owner}")

    def __set__(self, instance: Any, value: Any) -> None:
        raise AttributeError(
            "InputField instance is not supposed to be set with a value."
        )

    def __get__(self, instance: Any, owner: Any) -> Any:
        """
        Docstring for __get__

        :param instance: the instance of the owner class
        :type instance: Any {usually ModelForm]}
        :param owner: the owner class
        :type owner: Any [usually type[ModelForm]]
        :return: an instance of class that can be used to validate
        :rtype: Any
        """

        return self.proxy_class(instance, self._name, self)

    def opts(self, **kwargs: Any) -> Self:
        # this relay the options to forminput or validator
        self._forminput.opts(**kwargs)

    @cached_property
    def _forminput(self) -> f.BaseInput:
        return self.forminput(label=self.label, inputfield=self)


class StringField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        max_length: int | None = None,
        validator: v.Validator = v.String,
        forminput: f.FormField = f.TextInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            max_length=max_length,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class AlphanumPlusField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        max_length: int | None = None,
        validator: v.Validator = v.AlphanumPlus,
        forminput: f.FormField = f.TextInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            max_length=max_length,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class AlphanumField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        max_length: int | None = None,
        validator: v.Validator = v.Alphanum,
        forminput: f.FormField = f.TextInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            max_length=max_length,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class UUIDField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.UUID,
        forminput: f.FormField = f.TextInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


def EmailField(
    label: str,
    required: bool = False,
    max_length: int | None = None,
    validator: v.Validator = v.Email,
    forminput: f.FormField = f.TextInput,
    **kwargs: Any,
) -> InputField:
    _validator = validator(
        required=required,
        max_length=max_length,
        **kwargs,
    )
    return InputField(label=label, validator=_validator, forminput=forminput)


def IntField(
    label: str,
    required: bool = False,
    validator: v.Validator = v.Int,
    forminput: f.FormField = f.TextInput,
    **kwargs: Any,
) -> InputField:
    _validator = validator(
        required=required,
        **kwargs,
    )
    return InputField(label=label, validator=_validator, forminput=forminput)


def FloatField(
    label: str,
    required: bool = False,
    validator: v.Validator = v.Float,
    forminput: f.FormField = f.TextInput,
    **kwargs: Any,
) -> InputField:
    _validator = validator(
        required=required,
        **kwargs,
    )
    return InputField(label=label, validator=_validator, forminput=forminput)


class ForeignKeyField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        foreignkey_for: str | None = None,
        text_from: str | None = None,
        validator: v.Validator = v.Int,
        forminput: f.FormField = f.SelectInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(
            label=label,
            validator=_validator,
            forminput=forminput,
            foreignkey_for=foreignkey_for,
            text_from=text_from,
            proxy_class=_ForeignKeyInputFieldProxy,
        )


class SelectField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        options: list[tuple[Any, str]] | None = None,
        option_callback: Any | None = None,
        validator: v.Validator = v.String,
        forminput: f.FormField = f.SelectInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            options=options,
            option_callback=option_callback,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class EnumKeyField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        foreignkey_for: str | None = None,
        validator: v.Validator = v.Int,
        forminput: f.FormField = f.EnumKeyInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(
            label=label,
            validator=_validator,
            forminput=forminput,
            foreignkey_for=foreignkey_for,
            proxy_class=_EnumKeyInputFieldProxy,
        )


class DBEnumKeyField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        foreignkey_for: str | None = "category",
        validator: v.Validator = v.Int,
        forminput: f.FormField = f.SelectInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(
            label=label,
            validator=_validator,
            forminput=forminput,
            foreignkey_for=foreignkey_for,
            text_from="key",
            proxy_class=_DBEnumKeyInputFieldProxy,
        )


class CheckboxField(InputField):

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.Boolean,
        forminput: f.FormField = f.CheckboxInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


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
    This class functions as DTO, data validator, and HTML form generator
    """

    model_type: type[Any] | None = None
    exclude: list[str] | None = None
    include: list[str] | None = None
    only: list[str] | None = None

    __fields__: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically update class variable
        if hasattr(cls, "model_type"):
            if isinstance(cls.model_type, type):
                cls.model_name = cls.model_type.__name__
                cls.form_name = "lp-" + cls.model_name
                cls.controller_for_edit = cls.model_name.lower() + "-edit"
                cls.controller_for_update = cls.model_name.lower() + "-update"

    def __init__(
        self,
        obj: Any | None = None,
        data: dict[str, Any] = {},
        dbid: int = -1,
    ) -> None:
        self.obj: Any = obj
        self.data: dict[str, Any] = data
        self.dbid: int = (
            dbid if dbid >= 0 else (obj.id if (obj and hasattr(obj, "id")) else -1)
        )
        self.jscode: list[str] = []
        self.pyscode: list[str] = []
        self.scriptlinks: list[str] = []

    # override this method to set the layout
    async def set_layout(self, controller: Any = None) -> t.Tag:
        """
        Set the layout of the form
        """
        raise NotImplementedError("set_layout method must be implemented in subclass")

    # override this method to process integrity errors
    def process_integrity_error(
        self, error: exc.IntegrityError, data: dict[str, Any], dbsession: AsyncSession
    ) -> None:
        """
        Process the integrity error and raise DatabaseUpdateError if possible
        """
        raise error

    def validate(self, obj: Any, data: dict[str, Any]) -> None:
        """
        Validate the form data based on the obj
        """
        error_list = []

        for field_name in self.__fields__:
            if not hasattr(self, field_name):
                continue
            print("validating field:", field_name)
            field_validator: v.Validator = getattr(self, field_name)
            value = data.get(field_name, None)
            result, err_msg = field_validator.validate(value, obj=obj)
            if not result:
                error_list.append((f"Invalid {field_name}: {err_msg}", field_name))

        if any(error_list):
            raise ParseFormError(error_list)

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
                print(f"Field {field_name} is not defined in the form, skipping")
                continue
            if field_name not in data:
                print(f"Field {field_name} is not in the data, skipping")
                print(data)
                # field_name is not updated in the data
                continue
            field_validator: v.Validator = getattr(self, field_name)
            value = data.get(field_name)
            transformed_value = field_validator.transform(value)
            print("updating field:", field_name, "with value:", transformed_value)
            setattr(obj, field_name, transformed_value)

        # get database session of the object and flush to save changes
        try:
            await dbsession.flush()

        except exc.IntegrityError as e:
            # await dbsession.rollback()
            self.process_integrity_error(e, data, dbsession)

        except Exception as e:
            # this should convert to ParseFormError if possible
            # or updating flash messages
            raise e

    def check_timestamp(self, obj: Any, data: dict[str, Any]) -> None:
        """
        Check the timestamp of the object with the form data, and raise ParseFormError if the timestamp is invalid
        """
        form_stamp = data.get("stamp", None)
        obj_stamp = getattr(obj, "updated_at", None)
        if form_stamp is None or obj_stamp is None:
            raise ParseFormError([("Missing timestamp", "stamp")])
        if str(obj_stamp) != form_stamp:
            raise TimeStampError(
                "The data has been modified by another user or process. Please refresh and try again."
            )

    async def validate_and_update(
        self,
        data: dict[str, Any],
        dbsession: AsyncSession,
        check_timestamp: bool = True,
    ) -> None:
        """
        Validate and update the object with the form data
        """

        self.validate(self.obj, data)
        if check_timestamp:
            self.check_timestamp(self.obj, data)
        await self.update(self.obj, data, dbsession)

    async def html_form(
        self,
        request: Request,
        *,
        obj: Any = None,
        readonly: bool = False,
        editable: bool = False,
        controller: Any = None,
        errors: list[tuple[str, str]] = [],
    ) -> t.Tag:
        """
        Render the HTML form for creating or editing user domains
        """

        obj = obj or self.obj

        form_title = (
            f"Editing {self.model_name}" if obj else f"Create {self.model_name}"
        )
        submit_label = (
            "Edit" if readonly else ("Update" if (obj and obj.id) else "Create")
        )

        # generate form using tags_b53 module
        form = f.HTMLForm(
            name=self.form_name,
            method="post",
            action=request.url_for(
                self.controller_for_update,
                dbid=obj.id if (obj and obj.id) else 0,
            ),
            readonly=readonly,
        )[
            t.fieldset(name="hidden")[
                f.HiddenInput(
                    name="stamp", value=obj.updated_at if (obj and obj.id) else ""
                ),
            ],
            await self.set_layout(controller=controller),
            t.fieldset(name="footer")[
                (
                    t.a(
                        href=request.url_for(
                            self.controller_for_edit,
                            dbid=obj.id if (obj and obj.id) else 0,
                        ),
                        class_="btn btn-secondary",
                    )["Edit"]
                    if (editable and readonly)
                    else ""
                ),
                form_submit_bar(False) if (editable and not readonly) else "",
            ],
        ]

        await form.async_preprocess()

        if any(errors):
            for err_msg, field_name in errors:
                el = form.get_element(field_name)
                el.opts(error=err_msg)
                print(f"Set error for field {field_name}: {err_msg}")

        return dict(
            html=t.element()[
                self.header(),
                form,
            ],
            jscode="\n".join(self.jscode),
            pyscode="\n".join(self.pyscode),
            scriptlinks="\n".join(self.scriptlinks),
        )

    def header(self) -> t.htmltag:
        """
        Get the header for display purposes
        """
        html = t.element()[
            t.h2()[self.model_name],
            t.div()[
                t.span()[t.b()[" ID: "], self.obj.id if self.obj else ""],
                t.span()[
                    t.b()[" updated at: "],
                    ct.datetime(self.obj.updated_at) if self.obj else "",
                ],
                t.span()[
                    t.b()[" by: "],
                    (
                        self.obj.updated_by.login
                        if (self.obj and self.obj.updated_by)
                        else ""
                    ),
                ],
            ],
        ]
        return html


# EOF
