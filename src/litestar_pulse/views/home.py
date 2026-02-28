# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from litestar import Controller, Response, get, Request, MediaType

from litestar_pulse.views.baseview import LPController
from litestar_pulse.lib.template import Template
from litestar_pulse.templates.pages_b53 import base

import htpy as t


class HomeView(LPController):
    """
    HomeView is the view for the home page, and only handles / route.
    Application built on litestar-pulse should have its own implementation of home view.
    """

    path = "/"

    async def index(self) -> dict[str, str | t.Tag]:
        """
        Render the home page
        """

        user = self.req.user

        content = t.div()[
            t.h1()["litestar-pulse Library"],
            (
                t.p()["Your are logged in as: ", t.strong()[user.login]]
                if user
                else t.p()["You are not logged in."]
            ),
        ]

        return {"title": "Litestar Pulse Library", "body": content}

        return Template(template_name="lp_base.mako", content={"body": str(content)})

        return base(title="Litestar Pulse Library", content=content)

    @get(name="index")
    async def index_html(
        self, request: Request, db_session: AsyncSession, transaction: AsyncSession
    ) -> Template:
        """
        Render index page
        """
        request.logger.info("Rendering index page for %s", self.__class__.__name__)
        self.init_view(request, db_session, transaction)
        context = await self.index()
        return Template(template_name="lp/home.mako", context=context)

        return Response(content=str(content), media_type="text/html")


# EOF
