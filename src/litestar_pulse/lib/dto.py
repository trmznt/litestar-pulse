# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


# this module defines the data transfer objects schema used in Litestar-Pulse

from typing import Any, Protocol


class ValidatorP(Protocol):
    """
    This class only validate the data based on the rules defined in the validator
    """

    def validate(self, obj: Any, data: dict[str, Any]) -> tuple[bool, str | None]: ...

    def transform(self, value: Any) -> Any: ...


class InputFieldP(Protocol):
    """
    This class represent an input field that can be used in the form
    """


class ModelFormP(Protocol):
    """
    This class represent a form that can be used to validate and update a model
    """

    model_type: Any

    def set_layout(self, obj: Any = None) -> None:
        """
        Set the form fields based on the given object
        """


# EOF
