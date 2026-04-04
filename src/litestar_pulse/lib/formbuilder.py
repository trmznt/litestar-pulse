# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import json

from typing import Any, Self, Callable, Awaitable
from dataclasses import dataclass
from functools import cached_property

from sqlalchemy.orm import object_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import exc

from advanced_alchemy.exceptions import IntegrityError
from advanced_alchemy.types.file_object import FileObject, storages, FileObjectList

from litestar import Request

from tagato import tags as t, formfields as f

from . import validators as v
from . import compositetags as ct

from ..db.models.enumkey import EnumKeyRegistry


##
# Design Notes
# ============
#
# ModelForm():
# .field = InputField() -> _InputFieldProxy()
# .obj = the database object being edited
#
# InputField():
# ._name = field name set by __set_name__
# ._owner = <ModelForm> subclass where this field is declared
# ._forminput = tagato.BaseInput() -> warning! this might be incorrect!
#
# _InputFieldProxy():
# .owner_instance = ModelForm() instance this proxy is bound to
# .name = field name (same as InputField._name)
# .input_field = the InputField() descriptor this proxy is for
# .form_input = the tagato.BaseInput() instance from the InputField, with options populated
# .get_value() -> retrieves the current value for this field from the form data or DB object
# .validate() -> delegates to the InputField's validator
# .opts() -> forwards display options to the form_input widget
#
# most


class ParseFormError(ValueError):
    """Raised when form validation fails for one or more fields."""

    def __init__(self, error_list: list[tuple[str, str]]):
        """
        :param error_list: list of ``(message, field_name)`` tuples describing each error
        """
        super().__init__(f"Value error(s) in {len(error_list)} field(s): {error_list}")
        self.error_list = error_list


class DatabaseUpdateError(ValueError):
    """Raised when a database flush fails and can be attributed to a specific field."""

    def __init__(self, message: str, input_field: InputField):
        """
        :param message: human-readable error description
        :param input_field: the InputField instance that caused the error
        """
        super().__init__(message)
        self.input_field = input_field


class TimeStampError(ValueError):
    """Raised when the form's timestamp does not match the object's ``updated_at``.

    This indicates a concurrent modification conflict.
    """

    def __init__(self, message: str):
        super().__init__(message)


@dataclass
class _InputFieldProxy:
    """Proxy that bridges an InputField descriptor and a specific ModelForm instance.

    When a ModelForm instance accesses a field attribute (e.g. ``self.login``),
    the InputField descriptor returns a proxy that knows both the field
    definition and the current form data / database object.  The proxy is
    used for:
    - Retrieving the current value (from submitted data or the DB object)
    - Delegating validation and transformation to the underlying Validator
    - Generating the HTML form input via the tagato ``forminput`` class
    """

    owner_instance: Any  # the ModelForm instance
    name: str  # the field attribute name
    input_field: "InputField"  # the InputField descriptor instance

    def get_name(self) -> str:
        return self.name

    def get_value(self) -> Any:
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")

        if self.name in data:
            return data[self.name]
        if obj is not None:
            return getattr(obj, self.name, "") or ""
        return ""

    def get_options(self) -> list[tuple[int, str]] | None:
        return None

    def is_required(self) -> bool:
        return self.input_field.validator.required

    def validate(self, value: Any, obj: Any | None = None) -> tuple[bool, str]:
        return self.input_field.validator.validate(value, obj=obj)

    def transform(self, value: Any) -> Any:
        return self.input_field.validator.transform(value)

    @cached_property
    def form_input(self) -> f.BaseInput:
        return self.input_field.forminput(
            label=self.input_field.label,
            input_provider=self,
        )

    def opts(self, **kwargs: Any) -> Self:
        """Forward display options to the underlying form input widget."""
        self.form_input.opts(**kwargs)
        return self

    def __tag__(self) -> t.Tag:
        """Tagato rendering protocol — returns the form input widget."""
        return self.form_input


class _ForeignKeyInputFieldProxy(_InputFieldProxy):
    """Proxy for ForeignKeyField — resolves value as ``(id, display_text)`` tuple."""

    def opts(self, option_callback=None, **kwargs: Any) -> Self:
        if option_callback is not None:
            self.form_input.option_callback = option_callback
        self.form_input.opts(**kwargs)
        return self

    def get_value(self) -> tuple[int | None, str | None]:
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")
        if self.name in data:
            # if not self.input_field.required and data[self.name] == "":
            #    return (None, "")
            value = data[self.name]
            if value == "":
                return (None, "")
            value = int(value)
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
        return (None, "")


class _EnumKeyInputFieldProxy(_InputFieldProxy):
    """Proxy for EnumKeyField — resolves value from the in-memory EnumKeyRegistry."""

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
        return EnumKeyRegistry.get_all_items(category_key)


class _EnumKeyCollectionFieldProxy(_EnumKeyInputFieldProxy):
    """Proxy for EnumKeyCollectionField — resolves value from the in-memory EnumKeyRegistry."""

    def get_value(self) -> list[tuple[int, str]]:
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")
        values = []
        if self.name in data:
            raw_values = data[self.name]
            if isinstance(raw_values, str):
                raw_values = [v.strip() for v in raw_values.split(",") if v.strip()]
            for raw_value in raw_values:
                value = int(raw_value)
                ekey = EnumKeyRegistry.get_by_id(None, value)
                values.append((value, ekey.key))
            return values

        if obj is not None:
            related_objs = getattr(obj, self.name, [])
            for related_obj in related_objs:
                value = getattr(related_obj, "id", None)
                text = getattr(related_obj, self.input_field.text_from, "")
                values.append((value, text))
            return values
        return []

    def get_options(self) -> list[tuple[int, str]]:
        obj = getattr(self.owner_instance, "obj", None)
        if obj is None:
            raise RuntimeError("Owner instance does not have an 'obj' attribute")
        category_key = self.input_field.category_key
        if category_key is None:
            raise RuntimeError("Validator does not have 'category_key' set")

        return EnumKeyRegistry.get_all_items(category_key)


class _DBEnumKeyInputFieldProxy(_InputFieldProxy):
    """Proxy for DBEnumKeyField — resolves value from a DB-backed EnumKey relation."""

    def opts(self, option_callback=None, **kwargs: Any) -> Self:
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


class _FileUploadFieldProxy(_InputFieldProxy):
    """Proxy for FileUploadField — handles file upload validation and transformation."""

    def get_value(self) -> Any:
        """Override to return the uploaded file object instead of form data."""
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")

        if self.name in data:
            # the data dictionary has the uploaded file object from the request
            return data[self.name]  # this should be the uploaded file object

        if obj is not None:
            file_object: FileObject = getattr(obj, self.name, None)
            value = t.a(href=self.input_field)
            return file_object
        return None


class _MultipleFileUploadFieldProxy(_InputFieldProxy):
    """Proxy for MultipleFileUploadField — handles multiple file uploads."""

    def get_value(self) -> Any:
        """Override to return the list of uploaded file objects instead of form data."""
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")

        if self.name in data:
            # the data dictionary has the uploaded file objects from the request
            return data[self.name]  # this should be a list of uploaded file objects

        if obj is not None:
            file_objects: FileObjectList = getattr(obj, self.name, None)
            return file_objects
        return None


class _FilePondFieldProxy(_InputFieldProxy):
    """Proxy for FilePondField — handles file upload validation and transformation."""

    def get_value(self) -> Any:
        """
        Override to return the uploaded file object instead of form data.
        Form data is expected to have a field of {self.name}-selected-json
        which is a JSON string representing a list of selected file objects
        with 'id' and 'name' keys.
        """

        # get the instance object and the form data
        obj = getattr(self.owner_instance, "obj", None)
        data = getattr(self.owner_instance, "data")

        if self.name in data:
            # the data dictionary has the uploaded file object from the request
            # we need to combine this with the one in the instance itself.
            if f"{self.name}-:fileupload:json:" in data:
                # this should be the JSON string of selected file objects
                return data[f"{self.name}-:fileupload:json:"]

            # we need to access the JSON string from the form data, which should be in the format of {self.name}-selected-json
            return data[self.name]

        if obj is not None:
            file_objects: FileObjectList = getattr(obj, self.name, [])
            return file_objects

        return []

    def get_options(self) -> list[tuple[str, str]]:
        """
        Override to provide options for the FilePond input.
        This is to get the InputField's categories and use them as options for
        the FilePond input.
        """
        return self.input_field.categories


@dataclass
class InputField:
    """Descriptor that combines a Validator with a form input widget.

    When assigned as a class attribute on a ModelForm subclass, the Python
    descriptor protocol (``__set_name__`` / ``__get__``) automatically
    registers the field and returns a proxy bound to each form instance.

    Subclasses (StringField, ForeignKeyField, etc.) provide convenient
    constructors that wire up the appropriate validator and form widget.
    """

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

    # the proxy class to use when accessing this field on an instance
    proxy_class: type = _InputFieldProxy

    _FIELD_LIST_ATTR = "__fields__"

    def __post_init__(self) -> None:
        # Link the validator back to this InputField so it can lazily
        # resolve the attribute name via its cached_property._name
        self.validator.set_owner_instance(self)

    def __set_name__(self, owner: Any, name: str) -> None:
        """Called by Python when this descriptor is assigned to a class attribute.

        Registers the field name in the owner class's ``__fields__`` list so
        that ModelForm.validate / .update can iterate over all declared fields.
        """
        self._name = name  # name of the field
        # owner is usually the ModelForm subclass where this field is declared
        self._owner = owner

        if self._FIELD_LIST_ATTR not in owner.__dict__:
            setattr(owner, self._FIELD_LIST_ATTR, [])
        getattr(owner, self._FIELD_LIST_ATTR).append(name)

    def __set__(self, instance: Any, value: Any) -> None:
        raise AttributeError(
            "InputField instance is not supposed to be set with a value."
        )

    def __get__(self, instance: Any, owner: Any) -> _InputFieldProxy | Self:
        """Return the InputField class object when accessed on the class,
        or a cached proxy bound to the form instance when accessed on
        an instance.

        instance: the instance of the owner
        owner: the class where this descriptor is declared (usually a ModelForm subclass)
        returning the instance of inputfield proxy which has access to both the field definition and
        the form instance
        """
        if instance is None:
            return self

        # Cache proxies per-instance to avoid recreating them on every access
        proxy_cache = instance.__dict__.setdefault("_input_field_proxy_cache", {})
        if self._name not in proxy_cache:
            proxy_cache[self._name] = self.proxy_class(instance, self._name, self)

        return proxy_cache[self._name]

    def opts(self, **kwargs: Any) -> Self:
        # this relay the options to forminput or validator
        # not sure we need this
        raise NotImplementedError(
            "opts() should be implemented in the InputField proxy class."
        )
        self._forminput.opts(**kwargs)

    @cached_property
    def _forminput(self) -> f.BaseInput:
        raise RuntimeError("this should not be executed")
        print(f"Creating form input for field: {self!r}")
        return self.forminput(label=self.label, input_provider=self)

    async def async_prerender(
        self, controller: Any = None, field_proxy: _InputFieldProxy | None = None
    ) -> None:
        """Hook for subclasses that need async work before rendering.

        The default implementation is a no-op.  Override in field types
        that need to fetch options or perform other async setup.
        """

    async def _async_prerender_options(
        self, controller: Any = None, field_proxy: _InputFieldProxy | None = None
    ) -> None:
        """Populate select options via optional async callback."""

        form_input: f.BaseInput = (
            field_proxy.form_input if field_proxy is not None else self._forminput
        )

        option_async_callback = getattr(self, "option_async_callback", None)
        if form_input.get_options() is None and option_async_callback is not None:
            func = option_async_callback(controller)
            options = await func()
            if (
                form_input.input_provider
                and not form_input.input_provider.is_required()
            ):
                options = [("", "")] + options
            form_input.opts(options=options)
            # form_input.options = options


class StringField(InputField):
    """Text input field with string validation."""

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
    """Text input field that only accepts alphanumeric chars and ``+ - _ .``"""

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
    """Text input field that only accepts alphanumeric characters."""

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
    """Text input field with UUID format validation."""

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


class EmailField(InputField):
    """Text input field with email format validation."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        max_length: int | None = None,
        validator: v.Validator = v.Email,
        forminput: f.FormField = f.TextInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            max_length=max_length,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class IntField(InputField):
    """Text input field with integer validation."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.Int,
        forminput: f.FormField = f.TextInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class FloatField(InputField):
    """Text input field with float validation."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.Float,
        forminput: f.FormField = f.TextInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class YAMLField(InputField):
    """Text input field with YAML format validation."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.YAML,
        forminput: f.FormField = f.TextAreaInput,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(label=label, validator=_validator, forminput=forminput)


class ForeignKeyField(InputField):
    """Select input for foreign key relationships.

    Supports async option loading via ``option_async_callback``.
    """

    def __init__(
        self,
        label: str,
        required: bool = False,
        foreignkey_for: str | None = None,
        text_from: str | None = None,
        validator: v.Validator = v.ForeignKeyInt,
        forminput: f.FormField = f.SelectInput,
        option_async_callback: (
            Callable[[Any], Callable[[], Awaitable[list[tuple[str, str]]]]] | None
        ) = None,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            foreignkey_for=foreignkey_for,
            text_from=text_from,
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
        self.option_async_callback = option_async_callback

    async def async_prerender(
        self, controller: Any = None, field_proxy: _InputFieldProxy | None = None
    ) -> None:
        """Fetch options via callback if not already populated."""
        await self._async_prerender_options(controller, field_proxy)


class SelectField(InputField):
    """Generic select input field with static or async option lists."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        options: list[tuple[Any, str]] | None = None,
        option_callback: Any | None = None,
        validator: v.Validator = v.String,
        options_async_callback: (
            Callable[[Any], Callable[[], Awaitable[list[tuple[Any, str]]]]] | None
        ) = None,
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
        )
        # Store select-specific attributes on the field instance
        self.options = options
        self.option_callback = option_callback
        self.option_async_callback = options_async_callback

    async def async_prerender(
        self, controller: Any = None, field_proxy: _InputFieldProxy | None = None
    ) -> None:
        """Fetch options via callback if not already populated."""
        await self._async_prerender_options(controller, field_proxy)


class EnumKeyField(InputField):
    """Select input for in-memory EnumKey registries."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        foreignkey_for: str | None = None,
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
            proxy_class=_EnumKeyInputFieldProxy,
        )


class EnumKeyCollectionField(InputField):
    """Multiple select for SQLAlchemy collection relationship with EnumKey items."""

    def __init__(
        self,
        label: str,
        category_key: str,
        required: bool = False,
        foreignkey_for: str | None = None,
        validator: v.Validator = v.IntList,
        forminput: f.FormField = lambda **kwargs: f.SelectInput(
            multiple=True, **kwargs
        ),
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
            proxy_class=_EnumKeyCollectionFieldProxy,
        )
        self.category_key = category_key


class DBEnumKeyField(InputField):
    """Select input for database-backed EnumKey foreign keys."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        foreignkey_for: str | None = "category",
        validator: v.Validator = v.Int,
        forminput: f.FormField = f.SelectInput,
        option_async_callback: (
            Callable[[Any], Callable[[], Awaitable[list[tuple[str, str]]]]] | None
        ) = None,
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
        self.option_async_callback = option_async_callback

    async def async_prerender(
        self, controller: Any = None, field_proxy: _InputFieldProxy | None = None
    ) -> None:
        """Fetch options via callback if not already populated."""
        await self._async_prerender_options(controller, field_proxy)


class CheckboxField(InputField):
    """Checkbox input with boolean validation."""

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


class TomSelectField(InputField):
    """Select input rendered with TomSelect for enhanced UX."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        options: list[tuple[Any, str]] | None = None,
        option_callback: Any | None = None,
        validator: v.Validator = v.String,
        options_async_callback: (
            Callable[[Any], Callable[[], Awaitable[list[tuple[Any, str]]]]] | None
        ) = None,
        forminput: f.FormField = lambda **kwargs: f.SelectInput(
            always_show_input=True, **kwargs
        ),
        tom_select_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            label=label,
            required=required,
            options=options,
            option_callback=option_callback,
            validator=validator,
            options_async_callback=options_async_callback,
            forminput=forminput,
            **kwargs,
        )
        self.tom_select_options = tom_select_options or {}

    async def async_prerender(
        self, controller: Any = None, field_proxy: _InputFieldProxy | None = None
    ) -> None:
        """Fetch options and register TomSelect init code for this field."""
        await super().async_prerender(controller=controller, field_proxy=field_proxy)

        if field_proxy is None:
            return

        field_name = field_proxy.get_name()
        form_instance = field_proxy.owner_instance

        tom_options = {
            "create": False,
            "persist": False,
            "allowEmptyOption": True,
        }
        tom_options.update(self.tom_select_options)

        escaped_field_name = field_name.replace("\\", "\\\\").replace("'", "\\'")
        options_json = json.dumps(tom_options, ensure_ascii=True)

        form_instance.jscode.append(
            """
(function() {
    if (typeof TomSelect === 'undefined') {
        return;
    }
    var selector = "select[name='"""
            + escaped_field_name
            + """']";
    var element = document.querySelector(selector);
    if (!element || element.tomselect) {
        return;
    }
    new TomSelect(element, """
            + options_json
            + """);
})();
""".strip()
        )


class TomSelectEnumKeyCollectionField(InputField):
    """
    Multiple select with TomSelect for EnumKey collection relationships.
    Note need to changes the div class for read-only to:
        "ts-wrapper multi has-items"
    for proper styling with bootstrap 5.3
    """

    class _bs53_override_theme(f.Bootstrap53Theme):

        def select_class(self, *, error: bool = False) -> str:
            base = ""
            return f"{base} is-invalid" if error else base

    def __init__(
        self,
        label: str,
        category_key: str,
        required: bool = False,
        validator: v.Validator = v.IntList,
        forminput: f.FormField = lambda override_theme=_bs53_override_theme, **kwargs: f.SelectInput(
            multiple=True,
            always_show_input=True,
            override_theme=override_theme(),
            **kwargs,
        ),
        tom_select_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        _validator = validator(
            required=required,
            **kwargs,
        )
        super().__init__(
            label=label,
            required=required,
            validator=_validator,
            forminput=forminput,
            text_from="key",
            proxy_class=_EnumKeyCollectionFieldProxy,
        )
        self.category_key = category_key
        self.tom_select_options = tom_select_options or {}

    async def async_prerender(
        self, controller: Any = None, field_proxy: _InputFieldProxy | None = None
    ) -> None:
        """Register TomSelect init code for multiple EnumKey selection."""
        if field_proxy is None:
            return

        field_name = field_proxy.get_name()
        form_instance = field_proxy.owner_instance

        tom_options = {
            "create": False,
            "persist": False,
            "allowEmptyOption": True,
            "maxItems": None,  # allow unlimited selections for collection
        }
        tom_options.update(self.tom_select_options)

        escaped_field_name = field_name.replace("\\", "\\\\").replace("'", "\\'")
        options_json = json.dumps(tom_options, ensure_ascii=True)

        form_instance.jscode.append(
            """
(function() {
    if (typeof TomSelect === 'undefined') {
        return;
    }
    var selector = "select[name='"""
            + escaped_field_name
            + """']";
    var element = document.querySelector(selector);
    if (!element || element.tomselect) {
        return;
    }
    new TomSelect(element, """
            + options_json
            + """);
})();
""".strip()
        )


class FileUploadField(InputField):
    """File input field for uploading files."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.FileUpload,
        forminput: f.FormField = lambda **kwargs: f.FileInput(
            removal_flag="-retain-if-false!flag", **kwargs
        ),
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
            proxy_class=_FileUploadFieldProxy,
        )


class MultipleFileUploadField(InputField):
    """File input field for uploading multiple files."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.FileUploadList,
        forminput: f.FormField = ct.MultipleFileInput,
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
            proxy_class=_MultipleFileUploadFieldProxy,
        )


class PreUploadFileField(InputField):
    """File input field for uploading files."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.FileUpload,
        forminput: f.FormField = lambda **kwargs: f.FileInput(**kwargs),
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
            proxy_class=_FileUploadFieldProxy,
        )


class FilePondUploadField(InputField):
    """File input field rendered with FilePond for enhanced UX."""

    def __init__(
        self,
        label: str,
        required: bool = False,
        validator: v.Validator = v.FileUpload,
        forminput: f.FormField = ct.FilePondInput,
        categories: set[str] | None = None,
        filepond_options: dict[str, Any] | None = None,
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
            proxy_class=_FilePondFieldProxy,
        )
        self.filepond_options = filepond_options or {}
        # print(dir(self))
        # field = self._forminput
        # raise
        self.categories = [(o, o) for o in categories] if categories else None


# ------------------
#
#  Utilities
#
# ------------------


def form_submit_bar(create: bool = False) -> t.Tag:
    if create:
        return ct.custom_submit_bar(
            ("Add", "save"), ("Add and continue editing", "save_edit")
        ).set_offset(2)
    return ct.custom_submit_bar(
        ("Save", "save"), ("Save and continue editing", "save_edit")
    ).set_offset(2)


# ----------------
#
#  Main ModelForm class
#
# -----------------


class ModelForm:
    """Base class that combines DTO, data validation, and HTML form generation.

    Subclasses declare fields as class attributes using InputField descriptors
    (StringField, ForeignKeyField, etc.) and override ``set_layout()`` to
    define the HTML form structure.

    The class provides:
    - ``validate()`` — validates submitted data against all declared fields
    - ``update()`` — applies validated data to the database object
    - ``transform_and_update()`` — combines both with optimistic concurrency via timestamps
    - ``html_form()`` — renders a complete HTML form with error display
    """

    model_type: type[Any] | None = None
    exclude: list[str] | None = None
    include: list[str] | None = None
    only: list[str] | None = None

    __fields__: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Derive conventional names from model_type for form rendering and routing
        if cls.model_type is not None and isinstance(cls.model_type, type):
            cls.model_name = cls.model_type.__name__
            cls.form_name = "lp-" + cls.model_name
            cls.controller_for_edit = cls.model_name.lower() + "-edit"
            cls.controller_for_update = cls.model_name.lower() + "-update"

    def __init__(
        self,
        obj: Any | None = None,
        data: dict[str, Any] | None = None,
        dbid: int = -1,
    ) -> None:
        self.obj: Any = obj
        self.data: dict[str, Any] = data if data is not None else {}
        self.dbid: int = (
            dbid if dbid >= 0 else (obj.id if (obj and hasattr(obj, "id")) else -1)
        )
        self.jscode: list[str] = []
        self.pyscode: list[str] = []
        self.scriptlinks: list[str] = []

    # override this method to set the layout
    async def set_layout(self, controller: Any = None) -> t.Tag:
        """Define the form layout using tagato form fields.

        Must be overridden in subclasses to define the form structure.
        """
        raise NotImplementedError("set_layout method must be implemented in subclass")

    # override this method to process integrity errors
    def process_integrity_error(
        self, error: exc.IntegrityError, data: dict[str, Any], dbsession: AsyncSession
    ) -> None:
        """Convert an IntegrityError into a user-friendly DatabaseUpdateError.

        Override in subclasses to provide field-specific error messages
        for unique constraint violations, etc.
        """
        raise error

    def validate(self, obj: Any, data: dict[str, Any]) -> None:
        """Validate all declared fields against the submitted data.

        :param obj: the current database object (passed to validators for
            context-aware checks like allowing empty required fields on update)
        :param data: the submitted form data dict
        :raises ParseFormError: if any fields fail validation
        """
        error_list = []

        for field_name in self.__fields__:
            if not hasattr(self, field_name):
                continue
            field_validator = getattr(self, field_name)
            value = data.get(field_name, None)

            validator = field_validator.input_field.validator
            if validator.type == list and hasattr(data, "getall"):
                value = data.getall(field_name, [])

            result, err_msg = field_validator.validate(value, obj=obj)
            if not result:
                error_list.append((f"Invalid {field_name}: {err_msg}", field_name))

        if any(error_list):
            raise ParseFormError(error_list)

    def transform(self, obj: Any, data: dict[str, Any]) -> dict[str, Any]:
        """Transform submitted data into the format expected by the database object.

        This applies each field's transformation (type conversion, stripping,
        etc.) without actually setting the values on the object.  The resulting
        dict can be used for partial updates or other purposes.

        Flag attributes are those ending with "!flag" which indicate special handling
        (e.g. file removal) and are not passed to validators or transformed, but are
        being used to process the attributes in the transformed_data.

        -remove-if-false!flag, -retain-if-false!flag

        Attribute ATTR-remove-if-false!flag is used to indicate that ATTR should be removed
        from transformed_data if the ATTR is false (None, empty string, empty list, etc.)
        in the submitted data.
        For example, file uploads with an empty value indicates that the existing file should be retained.

        TODO:
        - need to handle list of fileobjects, so probably merging those in the data dict and obj

        :param obj: the current database object (passed to validators for context-aware transformations)
        :param data: the submitted form data dict
        :return: a new dict with transformed values for each field present in ``data``
        """

        transformed_data = {}
        error_list = []

        for field_name in self.__fields__:
            if not hasattr(self, field_name):
                continue
            if field_name not in data:
                continue
            field_validator = getattr(self, field_name)
            value = data.get(field_name)

            validator = field_validator.input_field.validator
            if validator.type == list and hasattr(data, "getall"):
                value = data.getall(field_name, [])

            result, err_msg = field_validator.validate(value, obj=obj)
            if not result:
                error_list.append((f"Invalid {field_name}: {err_msg}", field_name))
                continue

            transformed_value = field_validator.transform(value)
            transformed_data[field_name] = transformed_value

        if any(error_list):
            raise ParseFormError(error_list)

        # processed special flag attributes for transformations that are not handled
        # by validators, such as attribute removal flags
        for key in [s for s in data.keys() if s.endswith("-retain-if-false!flag")]:

            # if -retain-if-false!flag is not true, keep the existing value by not
            # including it in transformed_data as long as the
            attr_name = key.removesuffix("-retain-if-false!flag")
            if not data.pop(key):
                if not transformed_data.get(attr_name):
                    del transformed_data[attr_name]

        return transformed_data

    async def update(self, obj: Any, data: dict[str, Any], dbhandler: Any) -> None:
        """Apply transformed form data to the database object and flush.

        Only fields present in ``data`` are updated.

        :raises ValueError: if the object is not attached to a session
        :raises DatabaseUpdateError: if an IntegrityError occurs and
            ``process_integrity_error`` converts it
        """

        if object_session(obj) is None:
            raise ValueError("Object is not attached to a session")

        await self.before_update(obj, data, dbhandler.session)

        print("Updating object with data:", data)

        try:
            srv = dbhandler.get_service(self.model_type)
            await srv.update_from_dict(obj, data)

        except exc.IntegrityError as e:
            self.process_integrity_error(e, data, dbhandler.session)

        except IntegrityError as e:
            self.process_integrity_error(e.__cause__, data, dbhandler.session)

        except Exception:
            raise

    def check_timestamp(self, obj: Any, data: dict[str, Any]) -> None:
        """Verify optimistic concurrency by comparing timestamps.

        :raises ParseFormError: if the timestamp is missing
        :raises TimeStampError: if another user/process modified the record
        """
        form_stamp = data.get("stamp", None)
        obj_stamp = getattr(obj, "updated_at", None)
        if form_stamp is None or obj_stamp is None:
            raise ParseFormError([("Missing timestamp", "stamp")])
        if str(obj_stamp) != form_stamp:
            raise TimeStampError(
                "The data has been modified by another user or process. Please refresh and try again."
            )

    async def before_update(
        self, obj: Any, data: dict[str, Any], dbsession: AsyncSession
    ) -> dict[str, Any]:
        """Hook for performing actions before updating the object.

        Override in subclasses to implement custom pre-update logic, such as
        modifying data, performing additional validation, etc.
        """
        return data

    async def transform_and_update(
        self,
        data: dict[str, Any],
        dbhandler: Any | None,
        check_timestamp: bool = True,
    ) -> None:
        """Validate, check concurrency, and persist form data in one step."""

        if check_timestamp:
            self.check_timestamp(self.obj, data)
        transformed_data = self.transform(self.obj, data)
        await self.update(self.obj, transformed_data, dbhandler)

    async def async_prerender(self, controller: Any = None) -> None:
        """Run async prerender hooks on all fields that need them.

        Delegates to each InputField's ``async_prerender`` method, which is
        a no-op by default and overridden by field types that need to fetch
        options or perform other async setup (e.g. ForeignKeyField, DBEnumKeyField).
        """
        for field_name in self.__fields__:
            field_proxy = getattr(self, field_name)
            await field_proxy.input_field.async_prerender(
                controller, field_proxy=field_proxy
            )

    async def html_form(
        self,
        request: Request,
        *,
        obj: Any = None,
        readonly: bool = False,
        editable: bool = False,
        controller: Any = None,
        errors: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Render the complete HTML form with header, layout, and submit bar.

        :param request: the Litestar request (used for URL generation)
        :param obj: override the form's object for rendering
        :param readonly: render the form in read-only mode
        :param editable: show an "Edit" button when ``readonly`` is True
        :param controller: application controller (passed to set_layout and prerender)
        :param errors: list of ``(message, field_name)`` tuples to display as field errors
        :return: dict with ``html``, ``jscode``, ``pyscode``, ``scriptlinks`` keys
        """
        obj = obj or self.obj
        if errors is None:
            errors = []

        form_title = (
            f"Editing {self.model_name}" if obj else f"Create {self.model_name}"
        )

        # generate form using forminputs module
        form = f.HTMLForm(
            name=self.form_name,
            method="post",
            action=request.url_for(
                self.controller_for_update,
                dbid=obj.id if (obj and obj.id) else 0,
            ),
            enctype="multipart/form-data",
            _readonly=readonly,
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
                        class_="btn btn-primary",
                    )["Edit"]
                    if (editable and readonly)
                    else ""
                ),
                form_submit_bar(False) if (editable and not readonly) else "",
            ],
        ]

        # Run async prerender hooks (e.g. fetch select options)
        await self.async_prerender(controller=controller)

        # Apply any validation errors to their respective form elements
        for err_msg, field_name in errors:
            el = form.get_element(field_name)
            el.opts(error=err_msg)

        return dict(
            html=t.fragment()[
                self.header(),
                t.hr,
                form,
            ],
            javascript_code="\n".join(self.jscode),
            pyscript_code="\n".join(self.pyscode),
            scriptlink_lines="\n".join(self.scriptlinks),
        )

    def header(self) -> t.htmltag:
        """
        Get the header for display purposes
        """
        html = t.fragment()[
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
                        else "-"
                    ),
                ],
            ],
        ]
        return html


# EOF
