from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar_pulse.lib.app import lp_initdb_function_factory
    from litestar_pulse.views.modelview import LPModelView


LP_PREFIX: str | None = None


def set_lp_prefix(prefix: str) -> None:
    global LP_PREFIX
    LP_PREFIX = prefix


def get_lp_prefix() -> str:
    if LP_PREFIX is None:
        raise ValueError(
            "LP_PREFIX is not set. "
            "Please set it using set_lp_prefix() before using get_lp_prefix()."
        )
    return LP_PREFIX


def get_lp_controllers(prefix="/") -> list[type[Any]]:

    set_lp_prefix(prefix)

    from .home import HomeView
    from .login import LoginView
    from .enumkey import EnumKeyView
    from .userdomain import UserDomainView
    from .user import UserView
    from .group import GroupView
    from .api_v1 import API_v1
    from .async_fileupload import AsyncFileUpload

    return [
        HomeView,
        LoginView,
        EnumKeyView,
        UserDomainView,
        UserView,
        GroupView,
        API_v1,
        AsyncFileUpload,
    ]


# EOF
