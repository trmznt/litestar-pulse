# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable


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
__request_handler__: ContextVar[Any | None] = ContextVar(
    "litestar_pulse_request_handler", default=None
)


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


def set_handler(handler: Any) -> None:
    """Bind a handler instance to the current async context (request/task)."""
    __request_handler__.set(handler)


def clear_handler() -> None:
    """Clear the handler bound to the current async context."""
    __request_handler__.set(None)


def get_handler() -> Any:
    """
    Get an instance of the handler based on the context request session using
    ContextVar

    Returns:
        An instance of the handler class which is correct for the current request context.
    """
    handler = __request_handler__.get()
    if handler is None:
        raise RuntimeError(
            "No request-scoped handler is available in this context. "
            "Ensure LPController.init_view() has been called for this request."
        )
    return handler


__initdb_function_factory__: Callable[..., Any] | None = None


def set_initdb_function_factory(func: Callable[..., Any]) -> None:
    """Set the global database initialization function for the application.

    Args:
        func: The database initialization function to set.
    """
    global __initdb_function_factory__
    __initdb_function_factory__ = func


def get_initdb_function_factory() -> Callable[..., Any]:
    """Get the global database initialization function for the application.

    Returns:
        The database initialization function.
    """
    if __initdb_function_factory__ is None:
        raise RuntimeError(
            "Database initialization function factory is not set. "
            "Please set it using set_initdb_function_factory()."
        )
    return __initdb_function_factory__


# EOF
