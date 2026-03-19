# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from litestar import response
from litestar.enums import MediaType

# context injector

__context_injector__ = []


# generate a decorator function that injects context into the template rendering function
def context_injector(func):
    global __context_injector__
    __context_injector__.append(func)


class Template(response.Template):
    def __init__(self, **kwargs):

        for func in __context_injector__:
            func(kwargs["context"])

        # Force the media type to HTML regardless of filename
        kwargs.setdefault("media_type", MediaType.HTML)
        super().__init__(**kwargs)


def render_to_response(
    template_name: str,
    context: dict[str, object] | None = None,
    status_code: int = 200,
) -> response.Template:
    return Template(
        template_name=template_name, context=context or {}, status_code=status_code
    )


# EOF
