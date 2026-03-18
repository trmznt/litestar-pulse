from tagato import tags as t

from litestar_pulse.lib import roles as r


def user_menu(request):
    """return a HTML for user menu, bootstrap-based"""
    # authhost = request.registry.settings.get("rhombus.authhost", "")
    # url_login = authhost + '/login?'
    # url_logout = authhost + '/logout?'
    authhost = None  # TODO: get authhost from config

    user_menu_html = t.ul(class_="nav navbar-nav navbar-right")
    if hasattr(request, "user") and request.user:
        user_menu_list = t.li(class_="nav-item active dropdown")[
            t.a(
                class_="nav-link dropdown-toggle",
                id="navbarUsermenu",
                role="button",
                data_bs_toggle="dropdown",
                aria_expanded="false",
            )[
                t.i(class_="fas fa-user-circle"),
                " " + request.user.login,
            ],
            t.div(
                class_="dropdown-menu dropdown-menu-end",
                aria_labelledby="navbarUsermenu",
            )[
                (
                    t.a(
                        class_="dropdown-item",
                        href=request.url_for("user-view-id", dbid=request.user.id),
                    )["Profile"]
                    if not (request.user.has_roles(r.GUEST) or authhost)
                    else ""
                ),
                (
                    t.a(
                        class_="dropdown-item",
                        href=request.url_for("user-passwd", dbid=request.user.id),
                    )["Change password"]
                    if not (request.user.has_roles(r.GUEST) or authhost)
                    else ""
                ),
                (
                    t.a(
                        class_="dropdown-item",
                        href=request.url_for("home-index"),
                    )["Management"]
                    if request.user.has_roles(
                        [
                            r.SYSADM,
                            r.SYSVIEW,
                            r.DATAADM,
                            r.DATAVIEW,
                            r.ENUMKEY_VIEW,
                            r.USERDOMAIN_VIEW,
                            r.USER_VIEW,
                            r.GROUP_VIEW,
                        ]
                    )
                    else ""
                ),
                t.a(class_="dropdown-item", href=request.url_for("logout"))["Logout"],
            ],
        ]
    else:
        user_menu_list = t.li(class_="nav-item active")[
            t.a(class_="nav-link", href=request.url_for("login"))[
                t.i(class_="fas fa-sign-in-alt"), " Login "
            ]
        ]
    user_menu_html.add(user_menu_list)
    return user_menu_html

    # EOF
