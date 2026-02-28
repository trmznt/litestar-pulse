# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

from typing import Any
from sqlalchemy.orm import selectinload

from ..db.models.enumkey import EnumKey
from ..lib import roles as r
from .modelview import ModelForm, LPModelView, form_submit_bar, Request, ct, f, fb, t, v


class EnumKeyForm(fb.ModelForm):
    model_type = EnumKey
    exclude = ["id", "created_at", "updated_at"]
    include = None
    only = None

    key = fb.StringField(label="Key", required=True, max_length=64)
    desc = fb.StringField(label="Description", required=False, max_length=256)
    category_id = fb.ForeignKeyField(
        label="Category",
        required=False,
        foreignkey_for="category",
        text_from="key",
    )
    is_category = fb.CheckboxField(label="Category", required=False)

    async def set_layout(self, controller: Any = None) -> t.htmltag:
        form_layout = t.element()[
            f.fieldset(name="main")[
                f.InlineInput()[self.key.opts(_offset=2),],
                self.desc.opts(_offset=2, _size=5),
                f.CheckboxGroupInput(label="Options", _offset=2)[
                    self.is_category.opts(),
                ],
                self.category_id.opts(
                    _offset=2,
                    _option_callback=controller.dbh.repo.EnumKey.get_all_categories_for_options,
                ),
            ]
        ]

        return form_layout


class EnumKeyView(LPModelView):
    """
    EnumKeyView is the view for enum key management
    """

    path = "/enumkey"
    model_type = EnumKey
    model_form = EnumKeyForm
    title = "Enum Key Management"
    icon = "fa fa-list"

    managing_roles = LPModelView.managing_roles | {
        r.ENUMKEY_MODIFY,
        r.ENUMKEY_CREATE,
        r.ENUMKEY_DELETE,
    }
    viewing_roles = LPModelView.viewing_roles | {r.ENUMKEY_VIEW}

    def augment_repo_options(self, for_listing: bool = False) -> dict[str, Any]:
        """
        Augment repository options before execution.
        for_listing indicates if the operation is for listing multiple instances.
        """
        options = super().augment_repo_options(for_listing=for_listing)
        options.setdefault("load", []).append(selectinload(EnumKey.category))
        return options

    def generate_instance_table(
        self,
        enumkeys: list[EnumKey],
    ) -> tuple[t.htmltag, str]:
        return generate_enumkey_table(enumkeys, self.req)


def generate_enumkey_table(
    enumkeys: list[EnumKey], req: Request
) -> tuple[t.htmltag, str]:
    not_guest = True

    table_body = t.tbody()

    for enumkey in enumkeys:
        row = t.tr()[
            t.td()[
                (
                    t.literal(
                        '<input type="checkbox" name="enumkey-ids" value="%d" />'
                        % enumkey.id
                    )
                    if not_guest
                    else ""
                )
            ],
            t.td()[
                t.a(
                    href=req.url_for("enumkey-view-id", dbid=enumkey.id),
                )[enumkey.key]
            ],
            t.td()[enumkey.desc],
            t.td()[enumkey.category.key if enumkey.category else ""],
        ]

        table_body += row

    enumkey_table = t.table(
        id="enumkey-table", class_="table table-condensed table-striped"
    )[
        t.thead()[
            t.tr()[
                t.th(style="width: 2em"),
                t.th()["Key"],
                t.th()["Description"],
                t.th()["Category"],
            ]
        ]
    ]

    enumkey_table.add(table_body)

    if not_guest:
        add_button = ("New enum key", req.url_for("enumkey-edit", dbid=0))

        bar = ct.selection_bar(
            "enumkey-ids",
            action="/enumkey/action",
            add=add_button,
        )
        html, code = bar.render(enumkey_table)

    else:
        html = t.div()[enumkey_table]
        code = ""

    code += template_datatable_js
    return html, code


template_datatable_js = """
"""

# EOF
