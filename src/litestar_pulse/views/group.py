# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

# generate a vieew for Group model similar to User and UserDomain
from html import escape
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import object_session, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from litestar import Response, Request, get
from litestar.response import Redirect
from tagato import tags as t, formfields as f

from litestar_pulse.lib import roles as r
from litestar_pulse.db.models.account import Group, User, UserGroup
from .modelview import LPModelView, form_submit_bar
from ..lib import validators as v

# from ..lib import coretags as t
from ..lib import compositetags as ct

# from ..lib import forminputs as f
from ..lib import formbuilder as fb


class GroupForm(fb.ModelForm):
    model_type = Group
    exclude = ["id", "created_at", "updated_at"]
    include = None
    only = None

    name = fb.StringField(label="Group Name", required=True, max_length=64)
    desc = fb.StringField(label="Description", required=False, max_length=256)
    uuid = fb.UUIDField(label="UUID", required=False)
    roles = fb.TomSelectEnumKeyCollectionField(
        label="Roles",
        category_key="@ROLES",
        required=False,
    )

    async def set_layout(self, controller: Any = None) -> t.htmltag:
        form_layout = t.fragment(name="group-form")[
            f.fieldset(name="main")[
                f.InlineInput()[
                    self.name.opts(offset=2, size=2), self.uuid.opts(offset=1, size=3)
                ],
                self.desc.opts(offset=2, size=5),
                self.roles.opts(offset=2, size=5),
            ]
        ]
        return form_layout

    def process_integrity_error(
        self, error: Exception, data: dict[str, Any], dbsession: AsyncSession
    ) -> None:
        detail = error.args[0]
        if "UNIQUE" in detail or "UniqueViolation" in detail:
            if "groups.name" in detail or "uq_groups_name" in detail:
                name = data["name"]
                raise fb.ParseFormError(
                    [(f"Group name '{name}' already exists.", "name")]
                ) from error

        super().process_integrity_error(error, data, dbsession)


class GroupView(LPModelView):
    """
    GroupView is the view for group management
    """

    path = "/group"
    model_type = Group
    model_form = GroupForm
    title = "Group Management"
    icon = "fa fa-users"

    managing_roles = LPModelView.managing_roles | {r.GROUP_MANAGE}
    modiying_roles = LPModelView.modifying_roles | {r.GROUP_MODIFY}
    viewing_roles = LPModelView.viewing_roles | {r.GROUP_VIEW}

    def augment_repo_options(self, for_listing: bool = False) -> dict[str, Any]:
        """
        Augment repository options before execution.
        for_listing indicates if the operation is for listing multiple instances.
        """
        options = super().augment_repo_options(for_listing=for_listing)
        if for_listing:
            # defer loading roles for listing to improve performance, as it is not needed for the table view
            options.setdefault("load", []).extend(
                [
                    selectinload(Group.roles).defer("*"),
                    selectinload(Group.usergroups)
                    .selectinload(UserGroup.user)
                    .defer("*"),
                ]
            )

        # if not for_listing:
        #    # For single instance operations, eager load roles
        #    options.setdefault("load", []).extend(
        #        [
        #            selectinload(Group.roles),
        #            selectinload(Group.usergroups).selectinload(UserGroup.user),
        #        ]
        #    )
        return options

    def generate_instance_table(
        self,
        groups: list[Group],
    ) -> tuple[t.htmltag, str]:
        return generate_group_table(groups, self.req)

    async def get_bottom_panel(self, instance: Any) -> t.htmltag:

        usergroups = await instance.awaitable_attrs.usergroups
        if not any(usergroups):
            return None

        for ug in usergroups:
            print(f"UserGroup: {ug.user_id=}, {ug.group_id=}, {ug.role=}")

        html, code = generate_usergroup_table(usergroups, self.req)

        return dict(
            html=t.div(id="user-groups-panel")[t.h3["User Groups"], t.div()[html]],
            jscode=code,
        )


def generate_group_table(
    groups: list[Group], request: Request
) -> tuple[t.htmltag, str]:
    """
    Generate an HTML table for the given list of Group objects
    """
    not_guest = True

    table_body = t.tbody()

    for group in groups:
        row = t.tr()[
            t.td()[
                (
                    t.literal(
                        '<input type="checkbox" name="group-ids" value="%d" />'
                        % group.id
                    )
                    if not_guest
                    else ""
                )
            ],
            t.td()[
                t.a(
                    href=request.url_for("group-view-id", dbid=group.id),
                )[escape(group.name)]
            ],
            t.td()[escape(group.desc or "")],
            t.td()[ct.datetime(group.created_at)],
            t.td()[ct.datetime(group.updated_at)],
            t.td()[escape(group.updated_by_login)],
        ]
        table_body += row

    group_table = t.table(class_="table table-striped")[
        t.thead()[
            t.tr()[
                t.th()["ID"],
                t.th()["Name"],
                t.th()["Description"],
                t.th()["Created At"],
                t.th()["Updated At"],
                t.th()["Updated By"],
            ]
        ],
        table_body,
    ]

    if not_guest:
        add_button = ("New group", request.url_for("group-edit", dbid=0))

        bar = ct.selection_bar(
            "group-ids",
            action="/group/action",
            add=add_button,
        )
        html, code = bar.render(group_table)

    else:
        html = t.div()[group_table]
        code = ""

    code += template_datatable_js
    return html, code


def generate_usergroup_table(
    usergroups: list[Group], request: Request
) -> tuple[t.htmltag, str]:
    """
    Generate an HTML table for the given list of UserGroup objects
    """

    table_body = t.tbody()

    not_guest = True  # not request.user.has_roles(r.GUEST)

    for usergroup in usergroups:
        table_body.add(
            t.tr()[
                t.td()[
                    (
                        t.literal(
                            '<input type="checkbox" name="usergroup-ids" value="%d" />'
                            % usergroup.id
                        )
                        if not_guest
                        else ""
                    )
                ],
                t.td()[usergroup.user.login],
                t.td()[usergroup.role],
            ]
        )

    usergroup_table = t.table(
        id="usergroup-table", class_="table table-condensed table-striped"
    )[t.thead()[t.tr()[t.th(style="width: 2em"), t.th()["Login"], t.th()["Role"]]]]

    usergroup_table.add(table_body)

    if not_guest:
        add_button = ("New user-group", request.url_for("user-action", dbid=0))

        bar = ct.selection_bar(
            "usergroup-ids",
            action="/group/action",
            add=add_button,
        )
        html, code = bar.render(usergroup_table)

    else:
        html = t.div()[usergroup_table]
        code = ""

    code += template_datatable_js
    return html, code


template_datatable_js = """
"""


# EOF
