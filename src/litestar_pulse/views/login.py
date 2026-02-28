# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

import pickle
import msgspec

from sqlalchemy.ext.asyncio import AsyncSession

from litestar import Response, get, post, Request
from litestar.response import Redirect
from litestar.plugins.flash import flash

from litestar_pulse.db.models.account import User
from litestar_pulse.lib.auth import log_user_in
from litestar_pulse.views.baseview import Controller
from litestar_pulse.lib.template import Template
from litestar_pulse.lib import forminputs as fb
import htpy as t

from typing import TYPE_CHECKING

# TODO:
# - implement JWT-based authentication


class LoginView(Controller):
    path = ""

    @get("/login")
    async def login(self, request: Request) -> Template:
        """
        Render the login page
        """

        # check if form contains came_from, otherwise fill came_from
        # with url referrer or "/"
        form_data = await request.form()
        came_from = form_data.get("came_from", None) or request.headers.get(
            "Referer", "/"
        )
        username = form_data.get("username", "")

        return Template(
            template_name="lp/login.mako",
            context=dict(
                title="Litestar-Pulse",
                msg=(
                    "Wrong username or password"
                    if request.session.pop("failed_login", None)
                    else ""
                ),
                came_from=came_from,
                username=username,
            ),
        )

    @post("/login")
    async def do_login(self, request: Request, transaction: AsyncSession) -> Template:
        """
        Handle login form submission
        """
        form_data = await request.form()
        username = form_data.get("username")
        password = form_data.get("password")
        came_from = form_data.get("came_from", "/")

        user = await User.get_by_login(transaction, username)
        if not (user and await log_user_in(user, password, request)):
            request.set_session({"failed_login": True})
            return Redirect(path="/login", status_code=303)

        flash(request, "Login successful!", category="success")
        return Redirect(path=came_from, status_code=303)

        return Response(content=str(html), media_type="text/html")

    @get("/logout")
    async def logout(self, request: Request) -> Template:
        """
        Handle user logout
        """
        request.session.clear()

        body = t.div()[
            t.h1()["Logout Successful"],
            t.p()["You have been logged out."],
        ]

        return Template(
            template_name="lp_base.mako", context={"title": "Logout", "body": body}
        )

    @get("/login-remote")
    async def login_remote(self) -> Response[str]:
        """
        Check the request have JWST token and process the local auth session
        for future authenticated requests.
        Otherwise, redirect to remote identity provider login page.
        """
        html = t.html()

        return Response(content=str(html), media_type="text/html")


# EOF
