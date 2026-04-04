# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from typing import Any, TYPE_CHECKING
from pathlib import Path

import fastnanoid

if TYPE_CHECKING:
    from litestar import Request


def resources_to_paths(resources: list[str]) -> list:
    """Convert a list of resources to a path string.

    Args:
        resources: A list of resource strings.

    Returns:
        A path string.
    """

    paths = []
    for resource in resources:
        if ":" in resource:
            module, directory = resource.split(":", 1)
            # import module, and get its __file__ attribute
            mod = __import__(module, fromlist=["__file__"])
            path = Path(mod.__file__).parent
            if directory:
                path = path / directory
            paths.append(path)
        else:
            paths.append(Path(resource))

    return paths


def get_request_session_id(request: Request) -> str | None:
    """Return the current session id from Litestar scope/cookie fallbacks."""
    scope = request.scope

    # Server-side session middleware may expose the id under different keys.
    for key in ("_session_id", "session_id"):
        value = scope.get(key)
        if value:
            return str(value)

    session_obj = scope.get("session")
    if isinstance(session_obj, dict):
        for key in ("_session_id", "session_id", "id"):
            value = session_obj.get(key)
            if value:
                return str(value)

    # Fallback to the session cookie value when scope keys are unavailable.
    return request.cookies.get("session") or request.cookies.get("session_id")


# EOF
