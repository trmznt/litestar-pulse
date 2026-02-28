# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from sqlalchemy import select
from sqlalchemy.orm import object_session, undefer

from litestar import Response, Request, get
from litestar.response import Redirect

from litestar_pulse.lib import roles as r
from litestar_pulse.db.models.account import UserDomain

# from litestar_pulse.lib import tags_b53 as t

from litestar_pulse.lib import coretags as t
from litestar_pulse.lib import compositetags as ct
from litestar_pulse.lib import forminputs as f
from litestar_pulse.lib import validators as v
from litestar_pulse.lib import formbuilder as fb

from .modelview import LPModelView, form_submit_bar


from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserDomainForm(fb.ModelForm):
    model_type = UserDomain
    exclude = ["id", "created_at", "updated_at"]
    include = None
    only = None

    domain = fb.StringField(label="Domain", required=True, max_length=255)
    desc = fb.StringField(label="Description", required=False, max_length=1024)
    uuid = fb.UUIDField(label="UUID", required=False)
    domain_type_id = fb.EnumKeyField(
        label="Domain Type", required=True, foreignkey_for="domain_type"
    )

    async def set_layout(self, controller: Any = None) -> t.htmltag:
        form_layout = t.element()[
            f.fieldset(name="main")[
                f.InlineInput()[
                    self.domain.opts(_offset=2),
                    self.uuid.opts(_offset=1),
                ],
                self.desc.opts(_offset=2, _size=5),
                self.domain_type_id.opts(_offset=2, hidden=True),
            ]
        ]
        return form_layout

    def process_integrity_error(
        self, error: Exception, data: dict[str, Any], dbsession: AsyncSession
    ) -> None:
        detail = error.args[0]
        if "UNIQUE" in detail or "UniqueViolation" in detail:
            if "userdomains.domain" in detail or "uq_userdomains_domain" in detail:
                domain = data["domain"]
                raise fb.ParseFormError(
                    [(f"Domain '{domain}' already exists.", "domain")]
                ) from error

        super().process_integrity_error(error, data, dbsession)


class UserDomainView(LPModelView):
    """
    UserDomainView is the view for user domain management
    """

    path = "/userdomain"

    model_type = UserDomain
    model_form = UserDomainForm

    managing_roles = LPModelView.managing_roles | {
        r.USERDOMAIN_MODIFY,
        r.USERDOMAIN_CREATE,
        r.USERDOMAIN_DELETE,
    }
    viewing_roles = LPModelView.viewing_roles | {r.USERDOMAIN_VIEW}

    def generate_instance_table(
        self,
        userdomains: list[UserDomain],
    ) -> tuple[t.htmltag, str]:
        return generate_userdomain_table(userdomains, self.req)

    def augment_repo_options(self, for_listing: bool = False) -> dict[str, Any]:
        options = super().augment_repo_options(for_listing=for_listing)
        if for_listing:
            options.setdefault("load", []).append(undefer(UserDomain.user_count))
            options["order_by"] = [(UserDomain.domain, False)]
        return options


def generate_userdomain_table(
    userdomains: list[UserDomain], request: Request
) -> tuple[t.htmltag, str]:
    """
    Generate an HTML table for the given list of UserDomain objects
    """

    table_body = t.tbody()

    not_guest = True  # not request.user.has_roles(r.GUEST)

    for userdomain in userdomains:
        table_body.add(
            t.tr()[
                t.td()[
                    (
                        t.literal(
                            '<input type="checkbox" name="userdomain-ids" value="%d" />'
                            % userdomain.id
                        )
                        if not_guest
                        else ""
                    )
                ],
                t.td()[
                    t.a(
                        href=request.url_for("userdomain-view-id", dbid=userdomain.id),
                    )[userdomain.domain]
                ],
                t.td()[userdomain.desc],
                t.td()[userdomain.user_count],
            ]
        )

    userdomain_table = t.table(
        id="userdomain-table", class_="table table-condensed table-striped"
    )[
        t.thead()[
            t.tr()[
                t.th(style="width: 2em"),
                t.th()["Domain"],
                t.th()["Description"],
                t.th()["User Count"],
            ]
        ]
    ]

    userdomain_table.add(table_body)

    if not_guest:
        add_button = ("New user domain", request.url_for("userdomain-edit", dbid=0))

        bar = ct.selection_bar(
            "userdomain-ids",
            action="/userdomain/action",
            add=add_button,
        )
        html, code = bar.render(userdomain_table)

    else:
        html = t.div()[userdomain_table]
        code = ""

    code += template_datatable_js
    return html, code


template_datatable_js = """
"""

# EOF
