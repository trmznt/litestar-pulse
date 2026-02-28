# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from litestar import Request, Response, MediaType
from litestar.exceptions import NotFoundException
from litestar.exceptions.responses import create_debug_response
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR

from mako import exceptions as mako_exceptions


def handle_not_found(request: Request, exc: NotFoundException) -> Response:
    """Return a simple 404 page instead of invoking the debugger."""

    return create_debug_response(request, exc)

    html = f"""
    <html>
        <head>
            <title>404 - Not Found</title>
        </head>
        <body>
            <h1>Not Found</h1>
            <p>{exc.detail or 'The requested resource was not found.'}</p>
            <p>URL: {request.url}</p>
        </body>
    </html>
    """

    return Response(content=html, status_code=404, media_type="text/html")


def mako_html_exception_handler(request: Request, exc: Exception) -> Response:
    """
    Interacts with Mako's internal exception handling to render
    a specialized HTML error page for the browser.
    """
    # mako_exceptions.html_error_template() automatically uses sys.exc_info()
    # to find the last exception and render a rich traceback.
    error_html = mako_exceptions.html_error_template().render()

    return Response(
        content=error_html,
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        media_type=MediaType.HTML,
    )


# EOF
