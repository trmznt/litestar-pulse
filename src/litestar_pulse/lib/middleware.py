# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from typing import Any

from litestar_pulse.db import clear_handler


class HandlerContextMiddleware:
    """Guarantee request-local DB handler context is reset per request."""

    def __init__(self, app: Any, *args: Any, **kwargs: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        clear_handler()
        try:
            await self.app(scope, receive, send)
        finally:
            clear_handler()


# EOF
