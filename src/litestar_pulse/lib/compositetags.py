# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

# this module is based on https://github.com/trmznt/rhombus/blob/master/rhombus/lib/tags.py

from . import coretags as t


def datetime(dt):
    if dt is None:
        return ""
    return t.time(datetime=dt.isoformat())[dt.isoformat()]


class submit_bar(t.htmltag):

    def __init__(self, label="Save", value="save"):
        super().__init__()
        self.label = label
        self.value = value

    def __str__(self):
        return self.r()

    def r(self):
        html = t.div(class_="row mb-3")[
            t.div(class_="col-12 col-md-10 offset-md-3 d-flex gap-2 flex-wrap")[
                t.button(
                    name="_method",
                    class_="btn btn-primary",
                    type="submit",
                    value=self.value,
                )[self.label],
                t.button(type="reset", class_="btn btn-outline-secondary")["Reset"],
            ]
        ]
        return html.r()


class custom_submit_bar(t.htmltag):

    def __init__(self, *args):
        # args: ('Save', 'save'), ('Continue', 'continue')
        super().__init__()
        self.buttons = args
        self.offset = 3
        self.hide = False
        self.reset_button = True

    def set_offset(self, offset):
        self.offset = offset
        return self

    def set_hide(self, flag):
        self.hide = flag
        return self

    def show_reset_button(self, flag):
        self.reset_button = flag
        return self

    def r(self):
        html = t.div(class_="mb-3", style="display: none" if self.hide else "")
        buttons = t.div(
            class_="col-12 col-md-10 offset-md-%d d-flex flex-wrap gap-2" % self.offset
        )
        row = t.div(class_="row")[buttons]
        for b in self.buttons:
            assert type(b) == tuple or type(b) == list
            buttons.add(
                t.button(
                    class_="btn btn-primary",
                    type="submit",
                    name="_method",
                    id="_method.%s" % b[1],
                    value=b[1],
                )[b[0]]
            )
        if self.reset_button:
            buttons.add(
                t.button(class_="btn btn-outline-secondary", type="reset")["Reset"]
            )
        html.add(row)
        return html.r()


class selection_bar(object):

    def __init__(
        self,
        prefix,
        action,
        add=None,
        others="",
        hiddens=None,
        name="",
        delete_label="Delete",
        delete_value="delete",
    ):
        super().__init__()
        self.prefix = prefix
        self.action = action
        self.add = add
        self.others = others
        self.hiddens = list(hiddens or [])
        self.name = name or "selection_bar"
        self.delete_label = delete_label
        self.delete_value = delete_value

    def render(self, html, jscode=""):

        button_bar = t.div(class_="btn-toolbar gap-2 flex-wrap")[
            t.div(class_="btn-group me-2")[
                t.button(
                    type="button",
                    class_="btn btn-sm btn-secondary",
                    id=self.prefix + "-select-all",
                )["Select all"],
                t.button(
                    type="button",
                    class_="btn btn-sm btn-secondary",
                    id=self.prefix + "-select-none",
                )["Unselect all"],
                t.button(
                    type="button",
                    class_="btn btn-sm btn-secondary",
                    id=self.prefix + "-select-inverse",
                )["Inverse"],
            ],
            t.div(class_="btn-group me-2")[
                t.button(
                    class_="btn btn-sm btn-danger",
                    id=self.prefix + "-submit-delete",
                    name="_method",
                    value=self.delete_value,
                    type="button",
                )[
                    t.i(class_="fas fa-trash"),
                    self.delete_label,
                ]
            ],
        ]

        if self.add:
            button_bar.add(
                t.div(class_="btn-group me-2")[
                    t.a(href=self.add[1])[
                        t.button(type="button", class_="btn btn-sm btn-success")[
                            self.add[0]
                        ]
                    ]
                ]
            )

        if self.others:
            button_bar.add(t.div(class_="btn-group")[self.others])

        hiddens_container = None
        if self.hiddens:
            hiddens_container = t.div(class_="d-none")
            for k, v in self.hiddens:
                hiddens_container.add(t.input(type="hidden", name=k, value=v))

        form_id = f"{self.prefix}-form"
        sform = t.form(name=self.name, id=form_id, method="post", action=self.action)

        elements = [
            t.div(
                id=self.prefix + "-modal",
                class_="modal fade",
                role="dialog",
                tabindex="-1",
            ),
            button_bar,
            html,
        ]
        if hiddens_container:
            elements.append(hiddens_container)

        sform.add(*elements)

        return sform, jscode + selection_bar_js(form_id=form_id, prefix=self.prefix)


# text templates

SELECTION_BAR_JS_TEMPLATE = """\
(() => {{
    const prefix = "{prefix}";
    const init = () => {{
        const form = document.getElementById("{form_id}");
        if (!form) return;
        const modal = document.getElementById(`${{prefix}}-modal`);
        const checkboxSelector = 'input[name="{prefix}"]';

        const bind = (suffix, handler) => {{
            const node = document.getElementById(`${{prefix}}-${{suffix}}`);
            if (node) {{
                node.addEventListener('click', handler);
            }}
        }};

        const allBoxes = () => Array.from(form.querySelectorAll(checkboxSelector));

        bind('select-all', () => allBoxes().forEach(cb => (cb.checked = true)));
        bind('select-none', () => allBoxes().forEach(cb => (cb.checked = false)));
        bind('select-inverse', () => allBoxes().forEach(cb => (cb.checked = !cb.checked)));

        bind('submit-delete', async event => {{
            event.preventDefault();
            const button = event.currentTarget;
            try {{
                const formData = new FormData(form);
                if (button.name) {{
                    formData.set(button.name, button.value ?? '');
                }}

                const params = new URLSearchParams();
                formData.forEach((value, key) => {{
                    if (value instanceof File) {{
                        return;
                    }}
                    params.append(key, value);
                }});

                const response = await fetch(form.action, {{
                    method: form.method || 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest'
                    }},
                    body: params
                }});

                const text = await response.text();
                const target = modal || document;
                if (modal) {{
                    modal.innerHTML = text;
                    if (window.bootstrap && window.bootstrap.Modal) {{
                        window.bootstrap.Modal.getOrCreateInstance(modal).show();
                    }} else {{
                        modal.classList.add('show');
                        modal.style.display = 'block';
                    }}
                }}
                target.dispatchEvent(
                    new CustomEvent('selection-bar:loaded', {{ detail: {{ prefix, html: text }} }})
                );
            }} catch (error) {{
                console.error('Selection bar request failed', error);
            }}
        }});
    }};

    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', init, {{ once: true }});
    }} else {{
        init();
    }}
}})();
"""


def selection_bar_js(*, form_id: str, prefix: str) -> str:
    return SELECTION_BAR_JS_TEMPLATE.format(form_id=form_id, prefix=prefix)


# EOF
