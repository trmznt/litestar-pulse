# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from tagato import tags as t, formfields as f

from litestar import Response, Request, get, post
from litestar.response import Redirect
from litestar.exceptions import NotAuthorizedException
from litestar.plugins.flash import flash

from litestar_pulse.config.app import logger
from litestar_pulse.lib import roles as r
from litestar_pulse.db.models.account import User, UserGroup, Group
from .modelview import LPModelView, form_submit_bar, parse_indexed_form
from ..lib.template import Template
from ..lib import crypt
from ..lib import validators as v
from ..lib import compositetags as ct
from ..lib import formbuilder as fb
from ..lib.popup import modal_delete, modal_info, modal_submit


from typing import TYPE_CHECKING, Any


class UserForm(fb.ModelForm):
    model_type = User
    exclude = ["id", "created_at", "updated_at"]
    include = None
    only = None

    domain_id = fb.ForeignKeyField(
        label="Domain",
        required=True,
        foreignkey_for="domain",
        text_from="domain",
        option_async_callback=lambda ctrl: ctrl.dbh.repo.UserDomain.get_all_for_options,
    )
    login = fb.AlphanumPlusField(label="Login", required=True, max_length=32)
    email = fb.EmailField(label="Email", required=True, max_length=48)
    lastname = fb.StringField(label="Last Name", required=True, max_length=64)
    firstname = fb.StringField(label="First Name", required=True, max_length=64)
    institution = fb.StringField(label="Institution", required=True, max_length=128)
    uuid = fb.UUIDField(label="UUID", required=False)
    primarygroup_id = fb.ForeignKeyField(
        label="Primary Group",
        required=True,
        foreignkey_for="primarygroup",
        text_from="name",
        option_async_callback=lambda ctrl: ctrl.dbh.repo.Group.get_all_for_options,
    )
    attachment = fb.FileUploadField(label="Attachment", required=False)

    async def set_layout(self, controller: Any = None) -> t.htmltag:
        form_layout = t.fragment()[
            f.fieldset(name="main")[
                f.InlineInput()[
                    self.domain_id.opts(offset=2, size=3),
                    self.uuid.opts(offset=1, size=3),
                ],
                f.InlineInput()[
                    self.login.opts(offset=2, size=3),
                    self.email.opts(offset=1, size=3),
                ],
                f.InlineInput()[
                    self.lastname.opts(offset=2, size=3),
                    self.firstname.opts(offset=1, size=3),
                ],
                self.institution.opts(offset=2, size=5),
                self.primarygroup_id.opts(offset=2, size=3),
                self.attachment.opts(
                    offset=2,
                    size=5,
                    value=(
                        controller.get_attachment_url(self.obj) if controller else None
                    ),
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
            if "users.email" in detail or "uq_users_email" in detail:
                email = data["email"]
                raise fb.ParseFormError(
                    [(f"Email '{email}' already exists.", "email")]
                ) from error

        super().process_integrity_error(error, data, dbsession)


class UserView(LPModelView):
    """
    UserView is the view for user management
    """

    path = "/user"

    model_type = User
    model_form = UserForm

    managing_roles = LPModelView.managing_roles | {r.USER_MANAGE}
    modifying_roles = LPModelView.modifying_roles | {r.USER_MODIFY}
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

    async def get_bottom_panel(self, instance: Any) -> t.htmltag:

        usergroups = await instance.awaitable_attrs.usergroups

        html, code = generate_usergroup_table(usergroups, self.req)

        return dict(
            html=t.div(id="user-groups-panel")[t.h3["User Groups"], t.div()[html]],
            jscode=code,
        )

    # custom action

    async def additional_action(self, data: dict[str, Any]) -> Any:

        dbids = [int(x) for x in data.getall("usergroup-ids", [])]
        try:
            user_id = int(data.get("user-id", 0) or 0)
        except (TypeError, ValueError):
            user_id = 0

        match data.get("_method", None):

            case "usergroup-remove-confirmation":
                return await generate_usergroup_removal_popup(self, dbids)

            case "usergroup-remove-confirmed":
                await remove_usergroup(self, dbids)
                return Redirect(
                    path=self.req.url_for("user-view-id", dbid=user_id),
                    status_code=303,
                )

            case "usergroup-modify-confirmation":
                return await generate_usergroup_modify_role_popup(self, dbids)

            case "usergroup-modify-confirmed":
                await modify_usergroup_role(self, data)
                return Redirect(
                    path=self.req.url_for("user-view-id", dbid=user_id),
                    status_code=303,
                )

            case "usergroup-add-confirmation":
                return await generate_usergroup_add_popup(self, data)

            case "usergroup-add-confirmed":
                await add_usergroup(self, data)
                return Redirect(
                    path=self.req.url_for("user-view-id", dbid=user_id),
                    status_code=303,
                )

        return super().additional_action(data)

    # custom views

    @get(path="/{dbid:int}/passwd", name="passwd")
    async def passwd_id_html(
        self,
        dbid: int,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Template:
        """
        Custom view for editing user password
         - GET /user/{dbid}/passwd: show the password edit form
         - POST /user/{dbid}/passwd: handle the form submission and update the password
        """
        self.init_view(request, db_session, transaction)
        user = await self.get_model_instance(dbid=dbid)
        if not user:
            raise NotAuthorizedException("User not found")

        if request.user.id != user.id and not (
            request.user.has_roles(r.USER_MODIFY) or request.user.is_sysadm()
        ):
            raise NotAuthorizedException(
                "You do not have permission to change this user's password"
            )

        return Template(template_name="lp/passwd.mako", context={"request": request})

    @post(path="/{dbid:int}/passwd", name="passwd-update")
    async def passwd_update_id_html(
        self,
        dbid: int,
        request: Request,
        db_session: AsyncSession,
        transaction: AsyncSession,
    ) -> Template:
        """
        Handle the password update form submission
        """
        self.init_view(request, db_session, transaction)
        user = await self.get_model_instance(dbid=dbid)
        if not user:
            raise NotAuthorizedException("User not found")

        if request.user.id != user.id:
            if not (request.user.has_roles(r.USER_MODIFY) or request.user.is_sysadm()):
                raise NotAuthorizedException(
                    "You do not have permission to change this user's password"
                )
            current_user = await self.dbh.repo.User.get_one_or_none(id=request.user.id)
            user_credential = current_user.credential if current_user else None
        else:
            user_credential = user.credential

        if user_credential is None:
            raise NotAuthorizedException(
                "Current user does not have a password set, cannot change password"
            )

        form_data = await request.form()
        current_password = form_data.get("cur_password")
        password = form_data.get("new_password")
        confirm_password = form_data.get("confirm_password")

        # validate current_password with user
        if not await crypt.verify_password(current_password, user_credential):
            raise fb.ParseFormError(
                [("Current password is incorrect", "current_password")]
            )
        # validate the form data
        if not password:
            raise fb.ParseFormError([("Password is required", "password")])
        if password != confirm_password:
            raise fb.ParseFormError([("Passwords must match", "confirm_password")])

        # update the user's password
        await user.set_password(password)
        await transaction.flush()

        logger.info(
            "Password updated for user %s by %s", user.login, request.user.login
        )

        flash(request, "Password updated successfully!", category="success")
        return Redirect(
            path=request.url_for("user-view-id", dbid=dbid), status_code=303
        )


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


def additional_usergroup_buttons(selection_bar: ct.selection_bar) -> t.htmltag:
    return t.fragment()[
        t.button(
            class_="btn btn-sm btn-warning",
            id=selection_bar.prefix + "-submit-modify",
            name="_method",
            value="usergroup-modify-confirmation",
            type="button",
        )[
            t.i(class_="bi bi-pencil-square"),
            " Modify role",
        ],
        t.button(
            class_="btn btn-sm btn-success",
            id=selection_bar.prefix + "-submit-add",
            name="_method",
            value="usergroup-add-confirmation",
            type="button",
        )[
            t.i(class_="bi bi-plus-circle-fill"),
            " Add to group",
        ],
    ]


def generate_usergroup_table(
    usergroups: list[UserGroup], request: Request
) -> tuple[t.htmltag, str]:
    """
    Generate an HTML table for the given list of UserGroup objects
    """

    table_body = t.tbody()

    not_guest = True  # not request.user.has_roles(r.GUEST)

    role_choices = dict(M="Member", A="Admin")

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
                t.td()[usergroup.group.name],
                t.td()[role_choices.get(usergroup.role, usergroup.role)],
            ]
        )

    usergroup_table = t.table(
        id="usergroup-table", class_="table table-condensed table-striped"
    )[t.thead()[t.tr()[t.th(style="width: 2em"), t.th()["Group"], t.th()["Role"]]]]

    usergroup_table.add(table_body)

    if not_guest:

        bar = ct.selection_bar(
            "usergroup-ids",
            action="/user/action",
            delete_label="Remove",
            delete_value="usergroup-remove-confirmation",
            add=None,  # add_button,
            additional_button_func=additional_usergroup_buttons,
            hidden_inputs={"user-id": str(request.path_params["dbid"])},
        )
        html, code = bar.render(usergroup_table)

    else:
        html = t.div()[usergroup_table]
        code = ""

    code += template_datatable_js
    return html, code


# popup helpers


async def generate_usergroup_removal_popup(
    controller: LPModelView, dbids: list[int]
) -> t.htmltag:

    if not any(dbids):
        return modal_info(
            title="No groups selected",
            content="No user groups were selected for removal.",
            request=controller.req,
        )

    dbh = controller.dbh

    usergroups = await dbh.repo.UserGroup.list(
        UserGroup.id.in_(dbids),
        load=[joinedload(UserGroup.user), joinedload(UserGroup.group)],
    )

    if not any(usergroups):
        return modal_info(
            title="User groups not found",
            content="The selected user groups were not found.",
            request=controller.req,
        )

    for usergroup in usergroups:
        if usergroup.user.primarygroup_id == usergroup.group.id:
            return modal_info(
                title="Invalid selection",
                content=t.fragment[
                    t.p[
                        f"The user cannot be removed from primary group: {usergroup.group.name}. "
                    ],
                    t.p["Please change the user primary group first."],
                ],
                request=controller.req,
            )

    return modal_delete(
        title=f"Remove from group membership",
        content=t.fragment()[
            t.p()[
                "Are you sure you want to remove the user from the following group(s): "
                + ", ".join([usergroup.group.name for usergroup in usergroups])
                + "?"
            ]
        ],
        request=controller.req,
        value="usergroup-remove-confirmed",
    )


async def remove_usergroup(controller: LPModelView, dbids: list[int]) -> Response:

    if not any(dbids):
        flash(controller.req, "No user groups selected for removal", category="warning")
        return

    dbh = controller.dbh

    usergroups = await dbh.repo.UserGroup.list(
        UserGroup.id.in_(dbids),
        load=[joinedload(UserGroup.user), joinedload(UserGroup.group)],
    )

    if not any(usergroups):
        flash(controller.req, "Selected user groups not found", category="error")
        return

    for usergroup in usergroups:
        if usergroup.user.primarygroup_id == usergroup.group.id:
            flash(
                controller.req,
                f"Cannot remove user from primary group: {usergroup.group.name}. Please change the user's primary group first.",
                category="error",
            )
            return

    usergroup_ids = [ug.id for ug in usergroups]
    await controller.dbh.repo.UserGroup.delete_many(usergroup_ids)

    flash(controller.req, "User group(s) removed successfully", category="success")


async def generate_usergroup_modify_role_popup(
    controller: LPModelView, dbids: list[int]
) -> t.htmltag:

    if not any(dbids):
        return modal_info(
            title="No groups selected",
            content="No user groups were selected for modification.",
            request=controller.req,
        )

    # set the parameters to usergroup[IDX][id] and usergroup[IDX][role]
    # for the form submission

    dbh = controller.dbh

    usergroups = await dbh.repo.UserGroup.list(
        UserGroup.id.in_(dbids),
        load=[joinedload(UserGroup.group)],
    )

    return modal_submit(
        title=f"Modify role in the group(s)",
        content=t.fragment()[
            t.table(class_="table table-condensed")[
                t.thead()[
                    t.tr()[
                        t.th()["Group"],
                        t.th()["Role"],
                    ]
                ],
                t.tbody()[
                    *[
                        t.tr()[
                            t.td()[usergroup.group.name],
                            t.td()[
                                t.input(
                                    type="hidden",
                                    name=f"usergroup[{usergroup.id}][id]",
                                    value=str(usergroup.id),
                                ),
                                t.select(name=f"usergroup[{usergroup.id}][role]")[
                                    *[
                                        t.option(
                                            value=role_code,
                                            selected=usergroup.role == role_code,
                                        )[role_text]
                                        for role_code, role_text in [
                                            ("M", "Member"),
                                            ("A", "Admin"),
                                        ]
                                    ]
                                ],
                            ],
                        ]
                        for usergroup in usergroups
                    ]
                ],
            ]
        ],
        request=controller.req,
        submit_label="Modify",
        submit_value="usergroup-modify-confirmed",
    )


async def modify_usergroup_role(
    controller: LPModelView, data: dict[str, Any]
) -> Response:

    usergroup_data = parse_indexed_form(data)["usergroup"]

    if not any(usergroup_data):
        flash(
            controller.req,
            "No user groups selected for modification",
            category="warning",
        )
        return

    dbh = controller.dbh

    usergroup_ids = [int(ug["id"]) for ug in usergroup_data if "id" in ug]

    usergroups = await dbh.repo.UserGroup.list(
        UserGroup.id.in_(usergroup_ids),
        load=[joinedload(UserGroup.user), joinedload(UserGroup.group)],
    )

    usergroup_dict = {ug.id: ug for ug in usergroups}

    for ug in usergroup_data:
        ug_id = int(ug.get("id", 0))
        if ug_id in usergroup_dict:
            usergroup = usergroup_dict[ug_id]
            new_role = ug.get("role")
            if new_role in ["M", "A"]:
                usergroup.role = new_role

    await dbh.repo.UserGroup.update_many(usergroups)

    flash(
        controller.req, "User group role(s) modified successfully", category="success"
    )


async def generate_usergroup_add_popup(
    controller: LPModelView, data: dict[str, Any]
) -> t.htmltag:

    try:
        user_id = int(data.get("user-id", 0) or 0)
    except (TypeError, ValueError):
        user_id = 0

    if not user_id:
        return modal_info(
            title="User not found",
            content="User not found for adding to group.",
            request=controller.req,
        )

    dbh = controller.dbh

    user = await dbh.repo.User.get_one_or_none(
        id=user_id, load=[selectinload(User.usergroups)]
    )  # need to load usergroups to disable groups that the user is already in

    if not user:
        return modal_info(
            title="User not found",
            content="User not found for adding to group.",
            request=controller.req,
        )

    usergroup_group_ids = {ug.group_id for ug in user.usergroups}

    groups = [
        group
        for group in await dbh.repo.Group.list()
        if group.id not in usergroup_group_ids
    ]

    table = t.table(
        # Initial state: one empty row
        x_data="{ rows: [{id: '', role: 'M'}] }"
    )[
        t.thead()[
            t.tr()[
                t.th()["Group"],
                t.th()["Role"],
                t.th()[
                    # Click to push a new object into the array
                    t.button(
                        type="button",
                        class_="btn border-0 bg-transparent text-success",
                        **{"x-on:click": "rows.push({id: '', role: 'M'})"},
                    )[t.literal("&#x2795;"), " Add row"]
                ],
            ]
        ],
        t.tbody()[
            # Loop through the rows array
            t.template(x_for="(row, index) in rows", **{":key": "index"})[
                t.tr()[
                    t.td()[
                        t.select(name="group-id", x_model="row.id")[
                            t.option(value="")["Select a group"],
                            *[
                                t.option(
                                    value=group.id,
                                    # Validation: Disable if ID is used in other rows
                                    **{
                                        "x-bind:disabled": (
                                            f"rows.some((r, i) => r.id === '{group.id}' && i !== index)"
                                        )
                                    },
                                )[group.name]
                                for group in groups
                            ],
                        ]
                    ],
                    t.td()[
                        t.select(name="role", x_model="row.role")[
                            t.option(value="M")["Member"],
                            t.option(value="A")["Admin"],
                        ]
                    ],
                    t.td()[
                        # Remove button (only shows if more than one row exists)
                        t.button(
                            type="button",
                            class_="btn border-0 bg-transparent text-danger",
                            **{"x-on:click": "rows.splice(index, 1)"},
                            x_show="rows.length > 1",
                        )[t.i(class_="bi bi-x-circle-fill")]
                    ],
                ]
            ]
        ],
    ]

    return modal_submit(
        title=f"Add user to group",
        content=table,
        request=controller.req,
        submit_label="Add",
        submit_value="usergroup-add-confirmed",
    )


async def add_usergroup(controller: LPModelView, data: dict[str, Any]) -> Response:

    try:
        user_id = int(data.get("user-id", 0) or 0)
    except (TypeError, ValueError):
        user_id = 0

    if not user_id:
        flash(controller.req, "User not found for adding to group.", category="error")
        return

    dbh = controller.dbh

    user = await dbh.repo.User.get_one_or_none(
        id=user_id, load=[selectinload(User.usergroups)]
    )  # need to load usergroups to check groups that the user is already in

    if not user:
        flash(controller.req, "User not found for adding to group.", category="error")
        return

    usergroup_group_ids = {ug.group_id for ug in user.usergroups}

    new_usergroups = []
    for group_id, role in zip(data.getall("group-id"), data.getall("role")):
        try:
            parsed_group_id = int(group_id)
        except (TypeError, ValueError):
            continue

        if role not in {"M", "A"}:
            continue

        if parsed_group_id and parsed_group_id not in usergroup_group_ids:
            new_usergroups.append(
                UserGroup(user_id=user_id, group_id=parsed_group_id, role=role)
            )

    if not new_usergroups:
        flash(
            controller.req, "No valid groups selected for adding.", category="warning"
        )
        return

    await dbh.repo.UserGroup.add_many(new_usergroups)

    flash(controller.req, "User added to group(s) successfully", category="success")


# EOF
