# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


import os
import pickle
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any


from litestar.middleware.session.server_side import (
    ServerSideSessionBackend,
    ServerSideSessionConfig,
)
from litestar.security.jwt import JWTAuth, JWTCookieAuth
from litestar.security.session_auth import SessionAuth, SessionAuthMiddleware
from litestar.middleware import AuthenticationResult
from litestar.exceptions import NotAuthorizedException  # Specific exception
from litestar.connection import ASGIConnection
from litestar.handlers import BaseRouteHandler


from litestar_pulse.db.models import account
from litestar_pulse.config.app import session_config, logger
from litestar_pulse.lib.crypt import verify_password


if TYPE_CHECKING:
    from litestar_pulse.db.models.account import User, UserInstance


class LPSessionAuthMiddleware(SessionAuthMiddleware):
    async def authenticate_request(
        self, connection: ASGIConnection
    ) -> AuthenticationResult:
        # Check if session exists in scope to avoid unnecessary processing
        if "session" not in connection.scope or not connection.scope["session"]:
            return AuthenticationResult(user=None, auth=None)

        try:
            return await super().authenticate_request(connection)
        except NotAuthorizedException:
            # Catch ONLY the "No session/user found" case
            # This ensures request.user is set to None instead of raising a 401
            return AuthenticationResult(user=None, auth=None)
        # Any other exception (e.g. DB error in retrieve_user_handler) will still raise 500


async def retrieve_user_handler(
    session: dict[str, Any], connection: "ASGIConnection[Any, Any, Any, Any]"
) -> account.UserInstance | None:
    d = session.get("user", None)
    logger.info("Retrieving user from session: %s", d)
    return account.UserInstance(**d) if d else None


session_auth = SessionAuth[account.UserInstance, ServerSideSessionBackend](
    retrieve_user_handler=retrieve_user_handler,
    authentication_middleware_class=LPSessionAuthMiddleware,
    # we must pass a config for a session backend.
    # all session backends are supported
    session_backend_config=session_config,
    # exclude any URLs that should not have authentication.
    # We exclude the documentation URLs, signup and login.
    exclude=["/schema", "/logout"],
)


def have_roles(*roles: str):
    """Dependency to check if the user has at least one of the specified roles."""

    async def dependency(
        connection: ASGIConnection, route_handler: BaseRouteHandler
    ) -> None:
        user = connection.user
        if user is None or not any(role in user.roles for role in roles):
            raise NotAuthorizedException("User does not have required roles.")
        return None

    return dependency


def is_admin(connection: ASGIConnection, route_handler: BaseRouteHandler) -> None:
    """Dependency to check if the user is an admin."""
    user = connection.user
    if user is None or "admin" not in user.roles:
        raise NotAuthorizedException("User is not an admin.")
    return None


async def log_user_in(user: User, plain_password: str, request: ASGIConnection) -> bool:
    """
    Verify a user's password against the stored hashed password.
    """

    if await verify_password(plain_password, user.credential):
        # set user info in web session
        request.set_session({"user": await user.user_instance()})
        return True
    return False


# EOF
