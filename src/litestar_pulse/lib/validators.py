# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import re
from functools import cached_property
from typing import Any
from dataclasses import dataclass

# Pre-compiled regex patterns for validation (avoids recompilation on each call)
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class _FieldValidator:
    """Provides field-level access to validation and value retrieval.

    Acts as a bridge between a model instance and a Validator, resolving
    the current field value from the model object and delegating
    validation/transformation to the owning Validator.
    """

    def __init__(self, owner_instance: Any, name: str, validator: Validator) -> None:
        self._owner_instance = owner_instance
        self._name = name
        self._validator = validator

    def get_value(self) -> Any:
        obj = getattr(self._owner_instance, "obj", None)
        if obj is not None:
            return getattr(obj, self._name, "") or ""
        return ""

    def validate(self, value: Any, obj: Any | None = None) -> tuple[bool, str]:
        return self._validator.validate(value, obj=obj)

    def transform(self, value: Any) -> Any:
        return self._validator.transform(value)


class _EnumKeyIntFieldValidator(_FieldValidator):
    """Field validator for EnumKey foreign key fields.

    Resolves the current value as a (id, text) tuple from the EnumKey
    proxy on the model class, and provides option lists for select inputs.
    """

    def get_value(self) -> tuple[int | None, str | None]:
        obj = getattr(self._owner_instance, "obj", None)
        if obj is not None:
            value = getattr(obj, self._name, None)
            text = ""
            if value is not None and self._validator.foreignkey_for is not None:
                text = getattr(obj, self._validator.foreignkey_for, "")
            return (value, text)
        return (None, None)

    def get_options(self) -> list[tuple[int, str]]:
        obj = getattr(self._owner_instance, "obj", None)
        if obj is None:
            raise RuntimeError("Owner instance does not have an 'obj' attribute")
        enumproxy_name = self._validator.foreignkey_for
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


class _ForeignKeyIntFieldValidator(_FieldValidator):
    """Field validator for standard foreign key integer fields.

    Resolves the current value as a (id, text) tuple by traversing
    the foreign key relationship on the model object.
    """

    def get_value(self) -> tuple[int | None, str | None]:
        obj = getattr(self._owner_instance, "obj", None)
        if obj is not None:
            value = getattr(obj, self._name, None)
            text = ""
            if value is not None and self._validator.foreignkey_for is not None:
                related_obj = getattr(obj, self._validator.foreignkey_for)
                text = getattr(related_obj, self._validator.text_from, "")
            return (value, text)
        return (None, None)


@dataclass
class Validator:
    """Declarative validator for form fields.

    Encapsulates validation rules (type, length, format) and transformation
    logic for converting raw form input into typed Python values.

    Validators are owned by InputField instances in formbuilder and should
    not be used as descriptors directly. The ``set_owner_instance`` method
    links a Validator back to its owning InputField so that the field name
    can be resolved lazily via the ``_name`` cached property.
    """

    type: type = str
    required: bool = False
    alphanum: bool = False
    alphanumplus: bool = False
    max_length: int | None = None
    uuid: bool = False
    email: bool = False
    strip: bool = True
    max_value: int | None = None
    min_value: int | None = None
    foreignkey_for: str | None = None
    text_from: str | None = None
    field_validator_class: type = _FieldValidator

    @cached_property
    def _name(self) -> str:
        """Lazily resolve the field name from the owning InputField.

        This is a cached_property because ``set_owner_instance`` is called
        during InputField.__post_init__ (before __set_name__ assigns the
        name), so the name must be resolved on first access rather than
        at construction time.
        """
        return self._owner_instance._name

    def set_owner_instance(self, owner_instance: Any) -> None:
        """Link this validator to its owning InputField."""
        self._owner_instance = owner_instance

    def validate(self, value: Any, obj: Any | None = None) -> tuple[bool, str]:
        """Validate the given value based on the validator's rules.

        :param value: the raw input value to validate
        :param obj: the current database object (used to allow empty required
            fields during updates when the object already has a value)
        :return: ``(True, "")`` on success, ``(False, error_message)`` on failure
        """
        # Allow empty values for non-required fields
        if not self.required and (value is None or value == ""):
            return (True, "")

        if self.strip and isinstance(value, str):
            value = value.strip()

        # Check required constraint — safely handle non-string values
        if self.required and (
            value is None or (isinstance(value, str) and value.strip() == "")
        ):
            # During updates, allow empty if the object already has a value
            if obj is not None and getattr(obj, self._name, None) is not None:
                return (True, "")
            return (False, "This field is required.")

        # Boolean validation (early return — bool rules differ from other types)
        if self.type == bool:
            if not isinstance(value, bool):
                if isinstance(value, str):
                    if value.lower() not in (
                        "true",
                        "1",
                        "yes",
                        "on",
                        "false",
                        "0",
                        "no",
                        "off",
                    ):
                        return (False, "This field must be a boolean value.")
                else:
                    return (False, "This field must be a boolean value.")
            return (True, "")

        # Numeric type validation
        if self.type in (int, float):
            try:
                numeric_value = self.type(value)
            except (ValueError, TypeError):
                type_name = self.type.__name__
                return (False, f"This field must be a valid {type_name}.")
            if self.min_value is not None and numeric_value < self.min_value:
                return (False, f"Value must be at least {self.min_value}.")
            if self.max_value is not None and numeric_value > self.max_value:
                return (False, f"Value must be at most {self.max_value}.")

        # String format validations
        if self.alphanum and not str(value).isalnum():
            return (False, "This field must be alphanumeric.")

        if self.alphanumplus and not all(
            c.isalnum() or c in "+-_." for c in str(value)
        ):
            return (
                False,
                "This field must be alphanumeric or contain '+', '-', '.', or '_'.",
            )

        if self.max_length is not None and len(str(value)) > self.max_length:
            return (
                False,
                f"This field must be at most {self.max_length} characters long.",
            )

        # Use pre-compiled module-level regex patterns for performance
        if self.uuid and not _UUID_RE.match(str(value)):
            return (False, "This field must be a valid UUID.")

        if self.email and not _EMAIL_RE.match(str(value)):
            return (False, "This field must be a valid email address.")

        return (True, "")

    def transform(self, value: Any) -> Any:
        if self.strip and isinstance(value, str):
            value = value.strip()
        if self.type == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes", "on"):
                    return True
                elif value.lower() in ("false", "0", "no", "off"):
                    return False
                else:
                    raise ValueError("This field must be a boolean value.")
            raise ValueError("This field must be a boolean value.")
        if self.uuid and value == "":
            return None
        if not self.required and value == "":
            return None
        return self.type(value) if value is not None else None


def String(
    required: bool = False, strip: bool = True, max_length: int | None = None
) -> Validator:
    """Helper function to create a String Validator."""
    return Validator(
        type=str,
        required=required,
        strip=strip,
        max_length=max_length,
    )


def Int(
    required: bool = False, min_value: int | None = None, max_value: int | None = None
) -> Validator:
    """Helper function to create an Integer Validator."""
    return Validator(
        type=int,
        required=required,
        min_value=min_value,
        max_value=max_value,
    )


def EnumKeyInt(
    foreignkey_for: str,
    required: bool = False,
) -> Validator:
    """Helper function to create an Enum Key Integer Validator."""
    return Validator(
        type=int,
        required=required,
        foreignkey_for=foreignkey_for,
        text_from="key",
        field_validator_class=_EnumKeyIntFieldValidator,
    )


def ForeignKeyInt(
    foreignkey_for: str,
    text_from: str,
    required: bool = False,
) -> Validator:
    """Helper function to create a Foreign Key Integer Validator."""
    return Validator(
        type=int,
        required=required,
        foreignkey_for=foreignkey_for,
        text_from=text_from,
        field_validator_class=_ForeignKeyIntFieldValidator,
    )


def Float(
    required: bool = False,
    min_value: float | None = None,
    max_value: float | None = None,
) -> Validator:
    """Helper function to create a Float Validator."""
    return Validator(
        type=float,
        required=required,
        min_value=min_value,
        max_value=max_value,
    )


def Alphanum(
    required: bool = False, strip: bool = True, max_length: int | None = None
) -> Validator:
    """Helper function to create an Alphanumeric Validator."""
    return Validator(
        type=str,
        required=required,
        alphanum=True,
        strip=strip,
        max_length=max_length,
    )


def AlphanumPlus(
    required: bool = False, strip: bool = True, max_length: int | None = None
) -> Validator:
    """Helper function to create an AlphanumPlus Validator."""
    return Validator(
        type=str,
        required=required,
        alphanumplus=True,
        strip=strip,
        max_length=max_length,
    )


def UUID(required: bool = False) -> Validator:
    """Helper function to create a UUID Validator."""
    return Validator(
        type=str,
        required=required,
        uuid=True,
    )


def Email(required: bool = False, max_length: int = 64) -> Validator:
    """Helper function to create an Email Validator."""
    return Validator(
        type=str,
        required=required,
        email=True,
        max_length=max_length,
    )


def Boolean(required: bool = False) -> Validator:
    """Helper function to create a Boolean Validator."""
    return Validator(
        type=bool,
        required=required,
    )


# EOF
