# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from typing import TYPE_CHECKING, Any


__session_class__: type[Any] | None = None


def set_session_class(session_class: type[Any]) -> None:
    """Set the global session class for the application.

    Args:
        session_class: The session class to set.
    """
    global __session_class__
    __session_class__ = session_class


def session_factory() -> Any:
    """Create an instance of the global session class.

    Returns:
        An instance of the session class.
    """
    if __session_class__ is None:
        raise RuntimeError(
            "Session class is not set. Please set it using set_session_class()."
        )
    return __session_class__()


__handler_class__: type[Any] | None = None


def set_handler_class(handler_class: type[Any]) -> None:
    """Set the global handler class for the application.

    Args:
        handler_class: The handler class to set.
    """
    global __handler_class__
    __handler_class__ = handler_class


def handler_factory(session: Any) -> Any:
    """Create an instance of the global handler class with the given session.

    Args:
        session: The database session to use.

    Returns:
        An instance of the handler class.
    """
    if __handler_class__ is None:
        raise RuntimeError(
            "Handler class is not set. Please set it using set_handler_class()."
        )
    return __handler_class__(session)


# EOF
