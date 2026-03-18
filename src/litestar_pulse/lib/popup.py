# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"


from tagato import tags as t
from .template import Template


def popup(title, content, footer=None, request=None):

    ctx = {
        "title": title,
        "content": content,
        "footer": footer if footer else "",
        "jscode": "",
        "pyscode": "",
        "request": request,
    }
    return Template(template_name="lp/generics/popup.mako", context=ctx)


def modal_info(title, content, request):
    return popup(
        title=title,
        content=content,
        footer=t.fragment()[
            t.button(
                type="button",
                class_="btn btn-secondary",
                data_bs_dismiss="modal",
            )["Close"],
        ],
        request=request,
    )


def modal_submit(
    title, content, request, submit_label="Submit", submit_value="submit-confirmed"
):
    return popup(
        title=title,
        content=content,
        footer=t.fragment()[
            t.button(
                type="button",
                class_="btn btn-secondary",
                data_bs_dismiss="modal",
            )["Cancel"],
            t.button(
                class_="btn btn-primary",
                type="submit",
                name="_method",
                value=submit_value,
            )[submit_label],
        ],
        request=request,
    )


def modal_delete(title, content, request, value="delete-confirmed"):
    return popup(
        title=title,
        content=content,
        footer=t.fragment()[
            t.button(
                type="button",
                class_="btn btn-secondary",
                data_bs_dismiss="modal",
            )["Cancel"],
            t.button(
                class_="btn btn-danger",
                type="submit",
                name="_method",
                value=value,
            )["Confirm Delete"],
        ],
        request=request,
    )


def modal_error():
    raise NotImplementedError()


# EOF
