# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from collections.abc import Iterable
from types import ModuleType
from typing import Any
import sys


class SelectiveDebugger:
    """Wrap a debugger module but skip post-mortem for selected exception types."""

    def __init__(
        self,
        debugger: ModuleType | Any,
        *,
        excluded_exceptions: Iterable[type[BaseException]],
    ) -> None:
        self._debugger = debugger
        self._excluded = tuple(excluded_exceptions)

    def post_mortem(self, traceback=None):  # noqa: ANN001 - mirrors debugger signature
        exc = sys.exc_info()[1]
        if exc and isinstance(exc, self._excluded):
            return None
        return self._debugger.post_mortem(traceback)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._debugger, item)


# EOF
