# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from litestar import Response, Request, get

from litestar_pulse.lib import roles as r
from litestar_pulse.db.models.account import User
from .modelview import ModelForm, LPModelView, form_submit_bar
from ..lib import validators as v
from ..lib import coretags as t
from ..lib import compositetags as ct
from ..lib import forminputs as f
from ..lib import formbuilder as fb


from typing import TYPE_CHECKING, Any


class UserForm(fb.ModelForm):
    model_type = User
    exclude = ["id", "created_at", "updated_at"]
    include = None
    only = None

    domain_id = fb.ForeignKeyField(
        label="Domain", required=True, foreignkey_for="domain", text_from="domain"
    )
    login = fb.AlphanumPlusField(label="Login", required=True, max_length=32)
    email = fb.EmailField(label="Email", required=True, max_length=48)
    lastname = fb.StringField(label="Last Name", required=True, max_length=64)
    firstname = fb.StringField(label="First Name", required=True, max_length=64)
    institution = fb.StringField(label="Institution", required=False, max_length=128)
    uuid = fb.UUIDField(label="UUID", required=False)
    primarygroup_id = fb.ForeignKeyField(
        label="Primary Group",
        required=True,
        foreignkey_for="primarygroup",
        text_from="name",
    )

    async def set_layout(self, controller: Any = None) -> t.htmltag:
        form_layout = t.fragment()[
            f.fieldset(name="main")[
                f.InlineInput()[
                    self.domain_id.opts(
                        _offset=2,
                        _option_callback=controller.dbh.repo.UserDomain.get_all_for_options,
                    ),
                    self.uuid.opts(_offset=1),
                ],
                f.InlineInput()[
                    self.login.opts(_offset=2, _size=2),
                    self.email.opts(_offset=1, _size=4),
                ],
                f.InlineInput()[
                    self.lastname.opts(_offset=2, _size=3),
                    self.firstname.opts(_offset=1, _size=3),
                ],
                self.institution.opts(_offset=2, _size=5),
                self.primarygroup_id.opts(
                    _offset=2,
                    _size=3,
                    _option_callback=controller.dbh.repo.Group.get_all_for_options,
                ),
            ],
        ]
        return form_layout

    def process_integrity_error(
        self, error: Exception, data: dict[str, Any], dbsession: AsyncSession
    ) -> None:
        detail = error.args[0]
        if "UNIQUE" in detail or "UniqueViolation" in detail:
            if "users.login" in detail or "uq_users_login" in detail:
                login = data["login"]
                raise fb.ParseFormError(
                    [(f"Login '{login}' already exists.", "login")]
                ) from error

        super().process_integrity_error(error, data, dbsession)


class UserView(LPModelView):
    """
    UserView is the view for user management
    """

    path = "/user"

    model_type = User
    model_form = UserForm

    managing_roles = LPModelView.managing_roles | {
        r.USER_MODIFY,
        r.USER_CREATE,
        r.USER_DELETE,
    }
    viewing_roles = LPModelView.viewing_roles | {r.USER_VIEW}

    def augment_repo_options(self, for_listing: bool = False) -> dict[str, Any]:
        options = super().augment_repo_options(for_listing=for_listing)

        if for_listing:
            options["order_by"] = [(User.login, False)]

        return options

    def generate_instance_table(
        self,
        users: list[User],
    ) -> tuple[t.htmltag, str]:
        return generate_user_table(users, self.req)


def generate_user_table(users: list[User], request: Request) -> tuple[t.htmltag, str]:
    """
    Generate an HTML table for the given list of User objects
    """

    table_body = t.tbody()

    not_guest = True  # not request.user.has_roles(r.GUEST)

    for user in users:
        table_body.add(
            t.tr()[
                t.td()[
                    (
                        t.literal(
                            '<input type="checkbox" name="user-ids" value="%d" />'
                            % user.id
                        )
                        if not_guest
                        else ""
                    )
                ],
                t.td()[
                    t.a(
                        href=request.url_for("user-view-id", dbid=user.id),
                    )[user.login]
                ],
                t.td()[
                    t.a(
                        href=request.url_for("userdomain-view-id", dbid=user.domain.id)
                    )[user.domain.domain]
                ],
                t.td()[user.email],
            ]
        )

    user_table = t.table(id="user-table", class_="table table-condensed table-striped")[
        t.thead()[
            t.tr()[
                t.th(style="width: 2em"),
                t.th()["Login"],
                t.th()["UserDomain"],
                t.th()["Email"],
            ]
        ]
    ]

    user_table.add(table_body)

    if not_guest:
        add_button = ("New user", request.url_for("user-edit", dbid=0))

        bar = ct.selection_bar(
            "user-ids",
            action="/user/action",
            add=add_button,
        )
        html, code = bar.render(user_table)

    else:
        html = t.div()[user_table]
        code = ""

    code += template_datatable_js
    return html, code


template_datatable_js = """
"""

# EOF
