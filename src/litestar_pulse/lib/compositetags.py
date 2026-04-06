# SPDX-FileCopyrightText: 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

__copyright__ = "(C) 2025 Hidayat Trimarsanto <trimarsanto@gmail.com>"
__author__ = "trimarsanto@gmail.com"
__license__ = "MPL-2.0"

# this module is based on https://github.com/trmznt/rhombus/blob/master/rhombus/lib/tags.py

import json
from typing import Any
from markupsafe import escape, Markup

from tagato import tags as t, formfields as f


def datetime(dt):
    if dt is None:
        return ""
    return t.time(datetime=dt.isoformat())[dt.isoformat()]


class submit_bar(t.singletag):

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


class custom_submit_bar(t.singletag):

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
                    class_="btn btn-subtle-primary",
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
        prefix: str,
        action: str,
        add: tuple[str, str] | None = None,
        others: t.htmltag | str = "",
        hidden_inputs: dict[str, str | int] | None = None,
        name="",
        delete_label="Delete",
        delete_value="delete-confirmation",
        additional_button_func=None,
    ):
        """
        additional_button_func: a function that takes the selection_bar instance and returns
        a tag (eg. tag.fragment) to be added to the button bar. This can be used to add custom
        buttons with custom behavior.
        """

        super().__init__()
        self.prefix = prefix
        self.action = action
        self.add = add
        self.others = others
        self.hidden_inputs = hidden_inputs if hidden_inputs else {}
        self.name = name or "selection_bar"
        self.delete_label = delete_label
        self.delete_value = delete_value
        self.additional_button_func = additional_button_func

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
                    t.i(class_="bi bi-trash3-fill"),
                    " ",
                    self.delete_label,
                ]
            ],
        ]

        if additional_button_func := self.additional_button_func:
            button_bar.add(t.div(class_="btn-group me-2")[additional_button_func(self)])

        if self.add:
            button_bar.add(
                t.div(class_="btn-group me-2")[
                    t.a(href=self.add[1])[
                        t.button(type="button", class_="btn btn-sm btn-success")[
                            t.i(class_="bi bi-plus-circle-fill"), " ", self.add[0]
                        ]
                    ]
                ]
            )

        if self.others:
            button_bar.add(t.div(class_="btn-group")[self.others])

        hidden_container = None
        if any(self.hidden_inputs):
            hidden_container = t.div(class_="d-none")
            for k, v in self.hidden_inputs.items():
                hidden_container.add(t.input(type="hidden", name=k, value=v))

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
        if hidden_container:
            elements.append(hidden_container)

        sform.add(*elements)

        return sform, jscode + selection_bar_js(form_id=form_id, prefix=self.prefix)


# text templates

SELECTION_BAR_JS_TEMPLATE = """\
initSelectionBar("{form_id}", "{prefix}", "{checkbox_name}");
"""


def selection_bar_js(*, form_id: str, prefix: str, checkbox_name: str = None) -> str:
    """
    Generate initialization JavaScript for selection bar functionality.

    Args:
        form_id: HTML id of the form containing the checkboxes
        prefix: Prefix for button element IDs
        checkbox_name: Name attribute of checkbox inputs (defaults to prefix)

    Returns:
        JavaScript code that initializes selection bar behavior
    """
    checkbox_name = checkbox_name or prefix
    return SELECTION_BAR_JS_TEMPLATE.format(
        form_id=form_id, prefix=prefix, checkbox_name=checkbox_name
    )


# @
# Multiple file upload input


class MultipleFileInput(f.BaseInput):
    """
    A custom form input for handling advanced-alchemy FileObjectList directly.
    """

    def render_input(self, value: Any = None) -> t.Tag:
        theme = self._theme()
        readonly = self.is_readonly()

        # value should be a list of FileObject instances
        file_objects = (value if value is not None else self.get_value()) or []

        if readonly:
            # Show the filename as plain text in readonly mode (no input)
            return t.div(class_=theme.value_col(self.size))[
                t.div(class_="form-control-plaintext")[
                    (
                        t.ul[
                            [
                                t.li[escape(f.metadata.get("filename"))]
                                for f in file_objects
                            ]
                        ]
                        if any(file_objects)
                        else "No files"
                    )
                ]
            ]

        return t.div(class_=theme.value_col(self.size))[
            t.div(class_="form-control-plaintext")[
                (
                    [
                        t.div[
                            f.CheckboxInput(
                                name=self.name + "-list",
                                value=file_obj.filename,
                                label=escape(file_obj.metadata.get("filename")),
                            )
                        ]
                        for file_obj in file_objects
                    ]
                    if any(file_objects)
                    else "No files"
                )
            ],
            t.input(
                type="file",
                id=self.id,
                name=self.name,
                class_="filepond " + theme.input_class(error=bool(self.error)),
                placeholder=self.placeholder,
                style=self.input_style,
                readonly=readonly,
                multiple=True,
            ),
            theme.error_feedback(self.error),
        ]


def render_fileobject_label(file_obj: Any, url_for: callable[[str], str]) -> t.Tag:
    filename, description, category = (
        (
            file_obj.metadata.get("filename"),
            file_obj.metadata.get("description", ""),
            file_obj.metadata.get("category", ""),
        )
        if hasattr(file_obj, "metadata")
        else (str(file_obj), "", "")
    )
    file_url = url_for(file_obj.filename) if hasattr(file_obj, "filename") else "#"
    return t.fragment[
        t.a(href=file_url, target="_blank")[escape(filename)],
        t.div[
            category and t.span["[", escape(category), "] "],
            description and t.span[escape(description)],
        ],
    ]


def render_fileobject_list(
    fileobject_list: list[Any], url_for: callable[str, str]
) -> t.Tag | str:

    if not any(fileobject_list):
        return "No files"

    html = t.ul[[t.li[render_fileobject_label(f, url_for)] for f in fileobject_list]]

    return html


class FilePondInput(f.BaseInput):
    """
    A custom form input for handling advanced-alchemy FileObjectList directly.
    """

    @staticmethod
    def _normalize_uploads(
        *, file_objects: list[Any], uploads: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Normalize uploads into Alpine-ready dicts with selection and metadata fields."""

        normalized: list[dict[str, Any]] = []

        if uploads:
            if isinstance(uploads, list):
                return uploads

            for key, value in uploads.items():
                if isinstance(value, dict):
                    upload_id = str(value.get("id", key))
                    upload_name = str(value.get("name", upload_id))
                    upload_selected = bool(value.get("selected", True))
                    upload_description = str(value.get("description", "") or "")
                    upload_category = str(value.get("category", "") or "")
                else:
                    upload_id = str(key)
                    upload_name = str(value)
                    upload_selected = True
                    upload_description = ""
                    upload_category = ""
                normalized.append(
                    {
                        "id": upload_id,
                        "name": upload_name,
                        "selected": upload_selected,
                        "description": upload_description,
                        "category": upload_category,
                    }
                )
            return normalized

        for file_obj in file_objects:
            if isinstance(file_obj, dict) and "id" in file_obj:
                normalized.append(file_obj)
                continue
            upload_id = str(
                getattr(file_obj, "path", "") or getattr(file_obj, "filename", "")
            )
            metadata = getattr(file_obj, "metadata", {}) or {}
            upload_name = str(metadata.get("filename") or upload_id)
            upload_description = str(metadata.get("description") or "")
            upload_category = str(metadata.get("category") or "")
            if upload_id:
                normalized.append(
                    {
                        "id": upload_id,
                        "name": upload_name,
                        "selected": True,
                        "description": upload_description,
                        "category": upload_category,
                    }
                )

        return normalized

    def render_input(self, value: Any = None) -> t.Tag:
        theme = self._theme()
        readonly = self.is_readonly()

        # value: [list[FileObject | str | None] | str | None]
        file_objects = (value if value is not None else self.get_value()) or []

        if readonly:

            url_for = (
                self.input_provider.url_for
                if self.input_provider
                else lambda filekey: "/"
            )

            # Show the filename as plain text in readonly mode (no input)
            return t.div(class_=theme.value_col(self.size))[
                t.div(class_="form-control-plaintext")[
                    render_fileobject_list(file_objects, url_for)
                ]
            ]

        upload_id = str(
            getattr(self, "uploadId", None)
            or getattr(self, "upload_id", None)
            or self.id
            or self.name
        )
        uploads_arg = getattr(self, "uploads", None)
        uploads_data = self._normalize_uploads(
            file_objects=file_objects, uploads=uploads_arg
        )
        uploads_json = json.dumps(uploads_data)
        input_class = "filepond " + theme.input_class(error=bool(self.error))

        option_list = self.get_options()
        category_options = []
        if option_list:
            for item in option_list:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    category_options.append(
                        {"value": str(item[0]), "label": str(item[1])}
                    )
                elif isinstance(item, dict):
                    category_options.append(
                        {
                            "value": str(item.get("value", "")),
                            "label": str(item.get("label", item.get("value", ""))),
                        }
                    )
        category_options_json = json.dumps(category_options)

        container_html = Markup(
            """
<div x-data='{
    uploads: (%s).map((item) => ({
        ...item,
        selected: item.selected !== false,
        description: item.description || "",
        category: String(item.category || "")
    })),
    fieldName: %s,
    uploadId: %s,
    categoryOptions: %s,

    truncateFilename(filename, maxLength = 80) {
        const name = String(filename || "");
        if (name.length <= maxLength) return name;

        const lastDot = name.lastIndexOf(".");
        if (lastDot <= 0 || lastDot === name.length - 1) {
            const head = Math.max(1, Math.floor((maxLength - 3) * 0.7));
            const tail = Math.max(1, maxLength - 3 - head);
            return name.slice(0, head) + "..." + name.slice(-tail);
        }

        const base = name.slice(0, lastDot);
        const ext = name.slice(lastDot + 1);
        const extWithDot = "." + ext;

        const reserved = 3 + extWithDot.length;
        const baseBudget = Math.max(2, maxLength - reserved);
        if (base.length <= baseBudget) {
            return base + extWithDot;
        }

        const tailBase = Math.min(8, Math.max(2, Math.floor(baseBudget * 0.35)));
        const headBase = Math.max(1, baseBudget - tailBase);
        return base.slice(0, headBase) + "..." + base.slice(-tailBase) + extWithDot;
    },

    addUploadedFile(file) {
        const uploadedId = file.serverId || file.id;
        const uploadedName = file.filename || (file.file && file.file.name) || uploadedId;
        if (!uploadedId) return;

        const exists = this.uploads.some((item) => item.id === uploadedId);
        if (!exists) {
            this.uploads.push({
                id: uploadedId,
                name: uploadedName,
                selected: true,
                description: "",
                category: ""
            });
        }
    },

    initCategorySelections() {
        if (!this.categoryOptions.length) return;

        this.uploads = this.uploads.map((item) => {
            const current = String(item.category || "");
            if (!current) {
                return { ...item, category: "" };
            }

            const byValue = this.categoryOptions.find(
                (opt) => String(opt.value) === current
            );
            if (byValue) {
                return { ...item, category: String(byValue.value) };
            }

            const byLabel = this.categoryOptions.find(
                (opt) => String(opt.label) === current
            );
            if (byLabel) {
                return { ...item, category: String(byLabel.value) };
            }

            return { ...item, category: "" };
        });
    },

    initFilePond() {
        const pond = FilePond.create(this.$refs.input, {
            server: {
                process: "/async-fileupload",
                patch: "/async-fileupload/",
                revert: null,
                restore: null,
                load: null,
                fetch: null,
            },
            chunkUploads: true,
            allowMultiple: true,
            allowRevert: false,

            onprocessfile: (error, file) => {
                if (error) return;

                this.addUploadedFile(file);

                setTimeout(() => {
                    pond.removeFile(file.id, { revert: false });
                }, 500);
            },

            onprocessfiles: () => {
                pond.getFiles().forEach((item) => {
                    if (item.status === 5) {
                        this.addUploadedFile(item);
                    }
                });

                setTimeout(() => {
                    pond.getFiles().forEach((item) => {
                        if (item.status === 5) {
                            pond.removeFile(item.id, { revert: false });
                        }
                    });
                }, 500);
            }
        });
    }
}' x-init='initCategorySelections(); initFilePond()'>

    <div :id='uploadId + "-list-container"' class='form-control-plaintext mb-2 space-y-2'>
        <input type='hidden'
             :name='fieldName + "-:fileupload:json:"'
             :value='JSON.stringify(uploads.map((item) => ({ id: item.id, name: item.name, selected: item.selected !== false, description: item.description || "", category: item.category || "" })))'>
        <div x-show='uploads.length === 0' class='text-body-secondary text-sm'>No files</div>
        <template x-for='(file, index) in uploads' :key='index'>
            <div class='d-flex align-items-start gap-2 mb-2'>
                <input type='checkbox'
                      :name='fieldName + "-:fileupload:item:"'
                       :value='file.id'
                       :id='"cb-" + uploadId + "-" + index'
                      x-model='file.selected'>

                <div class='flex-grow-1'>
                    <label :for='"cb-" + uploadId + "-" + index' :title='file.name' x-text='truncateFilename(file.name)' :class='file.selected ? "text-sm d-block" : "text-sm d-block text-body-secondary opacity-50"'></label>

                    <div class='d-flex gap-2 mt-1 align-items-center'>
                        <input type='text' class='form-control form-control-sm flex-grow-1' placeholder='Description' x-model='file.description'>

                        <select x-show='categoryOptions.length > 0' class='form-select form-select-sm w-auto' style='min-width: 12rem;' x-model='file.category'>
                            <option value=''>Select category</option>
                            <template x-for='option in categoryOptions' :key='option.value'>
                                <option :value='String(option.value)' :selected='String(option.value) === String(file.category || "")' x-text='option.label'></option>
                            </template>
                        </select>
                    </div>
                </div>

                <button type='button' @click='uploads.splice(index, 1)' class='text-red-500 text-xs'>
                    Remove
                </button>
            </div>
        </template>
    </div>

    <input type='file' x-ref='input' id='%s' name='%s' class='%s' placeholder='%s' style='%s' data-filepond-managed='alpine' multiple>

</div>
"""
            % (
                escape(uploads_json),
                escape(json.dumps(self.name)),
                escape(json.dumps(upload_id)),
                escape(category_options_json),
                escape(upload_id),
                escape(self.name),
                escape(input_class),
                escape(self.placeholder or ""),
                escape(self.input_style or ""),
            )
        )

        return t.div(class_=theme.value_col(self.size))[
            t.literal(container_html),
            theme.error_feedback(self.error),
        ]


# EOF
